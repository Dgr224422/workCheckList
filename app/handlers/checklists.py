from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.config import AppContext
from app.db import checklists
from app.services.auth import ensure_min_role
from app.ui.labels import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_CHECKLISTS,
    CHECKLISTS_ADD_STEP,
    CHECKLISTS_CREATE,
    CHECKLISTS_MARK,
    CHECKLISTS_REMINDER,
    CHECKLISTS_PHOTOS,
    CHECKLISTS_START,
    CHECKLISTS_TEMPLATES,
)
from app.utils.common import build_media_path, now_iso, today_date

router = Router()


class ChecklistCreateStates(StatesGroup):
    title = State()
    step_text = State()


class ChecklistAddStepStates(StatesGroup):
    step_text = State()


class ChecklistMarkStates(StatesGroup):
    run_id = State()


class ChecklistPhotoStates(StatesGroup):
    awaiting_photo = State()


class ReminderStates(StatesGroup):
    worker_id = State()
    title = State()
    schedule_type = State()
    schedule_value = State()


def _checklists_menu_kb(is_admin: bool) -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=CHECKLISTS_TEMPLATES)
    kb.button(text=CHECKLISTS_START)
    kb.button(text=CHECKLISTS_MARK)
    kb.button(text=CHECKLISTS_REMINDER)
    if is_admin:
        kb.button(text=CHECKLISTS_CREATE)
        kb.button(text=CHECKLISTS_ADD_STEP)
        kb.button(text=CHECKLISTS_PHOTOS)
    kb.button(text=BTN_BACK)
    kb.button(text=BTN_CANCEL)
    kb.adjust(2, 2, 2, 2)
    return kb


def _cancel_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_CANCEL)
    kb.button(text=BTN_BACK)
    kb.adjust(2)
    return kb


@router.message(F.text == BTN_CHECKLISTS)
async def checklists_menu(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    is_admin = await ensure_min_role(message.from_user.id, "admin", ctx)
    await message.answer(
        "Чек-листы — выберите действие:",
        reply_markup=_checklists_menu_kb(is_admin).as_markup(resize_keyboard=True),
    )


@router.message(F.text == CHECKLISTS_TEMPLATES)
async def checklists_templates(message: Message) -> None:
    templates = await checklists.list_templates()
    if not templates:
        await message.answer("Шаблоны не созданы.")
        return
    buttons = [
        [InlineKeyboardButton(text=f"▶ {t['title']}", callback_data=f"check_start:{t['id']}")]
        for t in templates
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите шаблон для запуска:", reply_markup=kb)


@router.callback_query(F.data.startswith("check_start:"))
async def checklists_start_callback(call: CallbackQuery) -> None:
    template_id = int(call.data.split(":")[1])
    run_id = await checklists.create_run(template_id, call.from_user.id, today_date())
    await _send_run_steps(call.message, run_id)
    await call.answer("Чек-лист запущен")


@router.message(F.text == CHECKLISTS_START)
async def checklists_start_menu(message: Message) -> None:
    await checklists_templates(message)


@router.message(F.text == CHECKLISTS_MARK)
async def checklists_mark_start(message: Message, state: FSMContext) -> None:
    await state.set_state(ChecklistMarkStates.run_id)
    await message.answer("Введите RUN_ID чек-листа:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ChecklistMarkStates.run_id)
async def checklists_mark_run(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    try:
        run_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введите числовой RUN_ID.")
        return
    await state.clear()
    await _send_run_steps(message, run_id)
    await checklists_menu(message)


@router.callback_query(F.data.startswith("check_done:"))
async def checklists_mark_step(call: CallbackQuery, state: FSMContext) -> None:
    run_step_id = int(call.data.split(":")[1])
    await checklists.mark_run_step(run_step_id, None, now_iso())
    run_id = await checklists.get_run_id_for_step(run_step_id)
    await state.set_state(ChecklistPhotoStates.awaiting_photo)
    await state.update_data(run_step_id=run_step_id, run_id=run_id)
    kb = ReplyKeyboardBuilder()
    kb.button(text="Без фото")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2)
    await call.answer("Шаг отмечен")
    await call.message.answer(
        "Шаг отмечен ✅\nЕсли нужно фото, отправьте его сейчас или нажмите 'Отмена'.",
        reply_markup=kb.as_markup(resize_keyboard=True),
    )


@router.message(F.text == CHECKLISTS_CREATE)
async def checklists_create_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(ChecklistCreateStates.title)
    await message.answer("Введите название шаблона:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ChecklistCreateStates.title)
async def checklists_create_title(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    title = message.text.strip()
    template_id = await checklists.create_template(title, message.from_user.id, now_iso())
    await state.update_data(template_id=template_id, step_order=1)
    await state.set_state(ChecklistCreateStates.step_text)
    kb = ReplyKeyboardBuilder()
    kb.button(text="Готово")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2)
    await message.answer("Введите первый шаг (или нажмите 'Готово'):", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(ChecklistCreateStates.step_text)
async def checklists_create_step(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    if message.text == "Готово":
        await state.clear()
        await message.answer("Шаблон создан.")
        await checklists_menu(message)
        return
    data = await state.get_data()
    template_id = data["template_id"]
    step_order = data["step_order"]
    await checklists.add_step(template_id, step_order, message.text.strip())
    await state.update_data(step_order=step_order + 1)
    await message.answer("Шаг добавлен. Введите следующий шаг или нажмите 'Готово'.")


@router.message(F.text == CHECKLISTS_ADD_STEP)
async def checklists_add_step_menu(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    templates = await checklists.list_templates()
    if not templates:
        await message.answer("Шаблоны не созданы.")
        return
    buttons = [
        [InlineKeyboardButton(text=t["title"], callback_data=f"check_add_step:{t['id']}")]
        for t in templates
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите шаблон:", reply_markup=kb)


@router.callback_query(F.data.startswith("check_add_step:"))
async def checklists_add_step_select(call: CallbackQuery, state: FSMContext) -> None:
    template_id = int(call.data.split(":")[1])
    await state.update_data(template_id=template_id)
    await state.set_state(ChecklistAddStepStates.step_text)
    await call.message.answer("Введите текст шага:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))
    await call.answer()


@router.message(ChecklistAddStepStates.step_text)
async def checklists_add_step_text(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    data = await state.get_data()
    template_id = data["template_id"]
    steps = await checklists.template_steps(template_id)
    await checklists.add_step(template_id, len(steps) + 1, message.text.strip())
    await state.clear()
    await message.answer("Шаг добавлен.")
    await checklists_menu(message)


@router.message(F.text == CHECKLISTS_REMINDER)
async def reminder_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(ReminderStates.worker_id)
    await message.answer("Введите ID сотрудника:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ReminderStates.worker_id)
async def reminder_worker_id(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    try:
        worker_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введите числовой ID.")
        return
    await state.update_data(worker_id=worker_id)
    await state.set_state(ReminderStates.title)
    await message.answer("Введите текст напоминания:")


@router.message(ReminderStates.title)
async def reminder_title(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    await state.update_data(title=message.text.strip())
    await state.set_state(ReminderStates.schedule_type)
    kb = ReplyKeyboardBuilder()
    kb.button(text="День недели")
    kb.button(text="Дата")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2, 1)
    await message.answer("Выберите тип расписания:", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(ReminderStates.schedule_type)
async def reminder_schedule_type(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    if message.text not in {"День недели", "Дата"}:
        await message.answer("Выберите 'День недели' или 'Дата'.")
        return
    await state.update_data(schedule_type=message.text)
    await state.set_state(ReminderStates.schedule_value)
    prompt = "Введите номер дня недели (0-6):" if message.text == "День недели" else "Введите дату (YYYY-MM-DD):"
    await message.answer(prompt)


@router.message(ReminderStates.schedule_value)
async def reminder_schedule_value(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    data = await state.get_data()
    schedule_type = data["schedule_type"]
    weekday = None
    exact_date = None
    if schedule_type == "День недели":
        try:
            weekday = int(message.text.strip())
        except ValueError:
            await message.answer("Введите число от 0 до 6.")
            return
        if weekday < 0 or weekday > 6:
            await message.answer("Введите число от 0 до 6.")
            return
    else:
        exact_date = message.text.strip()
        try:
            datetime.strptime(exact_date, "%Y-%m-%d")
        except ValueError:
            await message.answer("Введите дату в формате YYYY-MM-DD.")
            return

    await checklists.add_reminder(
        data["worker_id"],
        data["title"],
        weekday,
        exact_date,
        now_iso(),
    )
    await state.clear()
    await message.answer("Напоминание добавлено.")
    await checklists_menu(message)


@router.message(F.text == CHECKLISTS_PHOTOS)
async def checklist_photos(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    rows = await checklists.run_steps_recent_photos(limit=10)
    if not rows:
        await message.answer("Фото не найдены.")
        return
    for row in rows:
        caption = (
            f"RUN_ID={row['run_id']} шаг {row['run_step_id']} | "
            f"{row['text']} | {row['done_at']}"
        )
        try:
            await message.answer_photo(photo=FSInputFile(row["photo_path"]), caption=caption)
        except FileNotFoundError:
            await message.answer(f"Не найден файл: {row['photo_path']}")


@router.message(ChecklistPhotoStates.awaiting_photo, F.photo)
async def checklist_step_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    run_step_id = data["run_step_id"]
    target = build_media_path("checklists", str(run_step_id))
    await message.bot.download(message.photo[-1], destination=target)
    await checklists.mark_run_step(run_step_id, str(target), now_iso())
    await state.clear()
    await message.answer("Фото к шагу сохранено ✅")
    run_id = data.get("run_id")
    if run_id:
        await _send_run_steps(message, run_id)
    await checklists_menu(message)


@router.message(ChecklistPhotoStates.awaiting_photo)
async def checklist_step_photo_text(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await checklists_menu(message)
        return
    if message.text == "Без фото":
        data = await state.get_data()
        run_id = data.get("run_id")
        await state.clear()
        if run_id:
            await _send_run_steps(message, run_id)
        await checklists_menu(message)
        return
    await message.answer("Отправьте фото или нажмите 'Отмена'.")


async def _send_run_steps(message: Message, run_id: int) -> None:
    steps = await checklists.run_steps(run_id)
    if not steps:
        await message.answer("Шаги не найдены.")
        return
    buttons = [
        [InlineKeyboardButton(text=f"{'✅' if s['is_done'] else '⬜️'} {s['text']}", callback_data=f"check_done:{s['run_step_id']}")]
        for s in steps
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await message.edit_text(f"Чек-лист RUN_ID={run_id}. Нажмите, чтобы отметить шаг:", reply_markup=kb)
    except Exception:
        await message.answer(f"Чек-лист RUN_ID={run_id}. Нажмите, чтобы отметить шаг:", reply_markup=kb)
