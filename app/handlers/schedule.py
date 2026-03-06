from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.config import AppContext
from app.db import schedule
from app.services.auth import ensure_min_role
from app.ui.labels import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_SCHEDULE,
    SCHEDULE_ADD,
    SCHEDULE_VIEW,
)
from app.utils.common import now_iso

router = Router()


class ScheduleAddStates(StatesGroup):
    work_date = State()
    worker_name = State()
    shift_time = State()
    notes = State()


class ScheduleViewStates(StatesGroup):
    year_month = State()


def _schedule_menu_kb(is_admin: bool) -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=SCHEDULE_VIEW)
    if is_admin:
        kb.button(text=SCHEDULE_ADD)
    kb.button(text=BTN_BACK)
    kb.button(text=BTN_CANCEL)
    kb.adjust(2, 2)
    return kb


def _cancel_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_CANCEL)
    kb.button(text=BTN_BACK)
    kb.adjust(2)
    return kb


@router.message(F.text == BTN_SCHEDULE)
async def schedule_menu(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    is_admin = await ensure_min_role(message.from_user.id, "admin", ctx)
    await message.answer(
        "График смен — выберите действие:",
        reply_markup=_schedule_menu_kb(is_admin).as_markup(resize_keyboard=True),
    )


@router.message(F.text == SCHEDULE_ADD)
async def schedule_add_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(ScheduleAddStates.work_date)
    await message.answer("Введите дату (YYYY-MM-DD):", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ScheduleAddStates.work_date)
async def schedule_add_date(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await schedule_menu(message)
        return
    await state.update_data(work_date=message.text.strip())
    await state.set_state(ScheduleAddStates.worker_name)
    await message.answer("Введите имя сотрудника:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ScheduleAddStates.worker_name)
async def schedule_add_worker(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await schedule_menu(message)
        return
    await state.update_data(worker_name=message.text.strip())
    await state.set_state(ScheduleAddStates.shift_time)
    await message.answer("Введите время смены (например 10:00-18:00):", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ScheduleAddStates.shift_time)
async def schedule_add_time(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await schedule_menu(message)
        return
    await state.update_data(shift_time=message.text.strip())
    await state.set_state(ScheduleAddStates.notes)
    kb = ReplyKeyboardBuilder()
    kb.button(text="Пропустить")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2)
    await message.answer("Примечание (или 'Пропустить'):", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(ScheduleAddStates.notes)
async def schedule_add_notes(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await schedule_menu(message)
        return
    notes = None if message.text.strip().lower() == "пропустить" else message.text.strip()
    data = await state.get_data()
    payload = {
        "work_date": data["work_date"],
        "worker_name": data["worker_name"],
        "shift_time": data["shift_time"],
        "notes": notes,
        "created_by": message.from_user.id,
        "created_at": now_iso(),
    }
    await schedule.add_shift(payload)
    await state.clear()
    await message.answer("Смена добавлена.")
    await schedule_menu(message)


@router.message(F.text == SCHEDULE_VIEW)
async def schedule_view_start(message: Message, state: FSMContext) -> None:
    await state.set_state(ScheduleViewStates.year_month)
    await message.answer("Введите месяц (YYYY-MM):", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ScheduleViewStates.year_month)
async def schedule_view_month(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await schedule_menu(message)
        return
    year_month = message.text.strip()
    rows = await schedule.month_schedule(year_month)
    await state.clear()
    if not rows:
        await message.answer("Смен нет.")
        await schedule_menu(message)
        return
    lines = [
        f"{r['work_date']} | {r['worker_name']} | {r['shift_time']} | {r.get('notes') or ''}"
        for r in rows
    ]
    await message.answer("\n".join(lines[:100]))
    await schedule_menu(message)
