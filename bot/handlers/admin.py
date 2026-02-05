from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.handlers.states import AdminStates
from bot.keyboards import admin_keyboard, admin_panel_keyboard


router = Router()


def _is_admin(message: Message) -> bool:
    return message.from_user.id in message.bot["admin_ids"]


@router.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Эта функция доступна только администраторам.")
        return
    await message.answer("Админ-панель", reply_markup=admin_panel_keyboard)


@router.message(F.text == "➕ Создать чек-лист")
async def ask_checklist_title(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.set_state(AdminStates.creating_checklist)
    await message.answer("Введите название нового чек-листа:")


@router.message(AdminStates.creating_checklist)
async def create_checklist(message: Message, state: FSMContext) -> None:
    db = message.bot["db"]
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return

    try:
        checklist_id = await db.create_checklist(title)
    except Exception:
        await message.answer("Не удалось создать чек-лист. Возможно, такое название уже есть.")
        return

    await state.clear()
    await message.answer(
        f"Чек-лист создан: #{checklist_id} — {title}",
        reply_markup=admin_panel_keyboard,
    )


@router.message(F.text == "📋 Список чек-листов")
async def show_checklists(message: Message) -> None:
    if not _is_admin(message):
        return
    db = message.bot["db"]
    checklists = await db.list_checklists()
    if not checklists:
        await message.answer("Пока нет созданных чек-листов.")
        return

    lines = ["Список чек-листов:"]
    for checklist in checklists:
        items = await db.get_checklist_items(checklist.id)
        lines.append(f"{checklist.id}. {checklist.title} (пунктов: {len(items)})")
    await message.answer("\n".join(lines))


@router.message(F.text == "✏️ Добавить пункт")
async def ask_checklist_for_item(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return

    db = message.bot["db"]
    checklists = await db.list_checklists()
    if not checklists:
        await message.answer("Сначала создайте хотя бы один чек-лист.")
        return

    await state.set_state(AdminStates.adding_item_choose)
    items = "\n".join(f"{c.id}. {c.title}" for c in checklists)
    await message.answer(f"Выберите ID чек-листа для добавления пункта:\n{items}")


@router.message(AdminStates.adding_item_choose)
async def choose_checklist_for_item(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("Нужно отправить числовой ID чек-листа.")
        return

    checklist_id = int(text)
    db = message.bot["db"]
    checklists = await db.list_checklists()
    if checklist_id not in {c.id for c in checklists}:
        await message.answer("Чек-лист с таким ID не найден.")
        return

    await state.update_data(checklist_id=checklist_id)
    await state.set_state(AdminStates.adding_item_text)
    await message.answer("Введите текст пункта:")


@router.message(AdminStates.adding_item_text)
async def add_item(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст пункта не должен быть пустым.")
        return

    db = message.bot["db"]
    data = await state.get_data()
    checklist_id = data["checklist_id"]
    await db.add_checklist_item(checklist_id, text)
    await state.clear()
    await message.answer("Пункт добавлен.", reply_markup=admin_panel_keyboard)


@router.message(F.text == "📁 Отчеты сотрудников")
async def reports(message: Message) -> None:
    if not _is_admin(message):
        return

    db = message.bot["db"]
    reports_data = await db.list_all_submissions(limit=30)
    if not reports_data:
        await message.answer("Отчетов пока нет.")
        return

    lines = ["Последние отчеты:"]
    for submission_id, full_name, title, created_at in reports_data:
        lines.append(f"#{submission_id} | {full_name} | {title} | {created_at}")
    await message.answer("\n".join(lines), reply_markup=admin_panel_keyboard)


@router.message(F.text == "Главное меню")
async def main_menu(message: Message) -> None:
    if not _is_admin(message):
        return
    await message.answer("Главное меню", reply_markup=admin_keyboard)
