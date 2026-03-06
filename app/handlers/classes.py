from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.db import classes
from app.ui.labels import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_CLASSES,
    CLASSES_ADD,
    CLASSES_FIND,
)
from app.utils.common import build_media_path, now_iso

router = Router()


class ClassAddStates(StatesGroup):
    phone = State()
    tickets = State()
    cleanliness = State()
    behavior = State()
    school = State()
    district = State()
    session = State()
    rows = State()
    info = State()
    photo = State()


class ClassFindStates(StatesGroup):
    phone_part = State()


def _classes_menu_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=CLASSES_ADD)
    kb.button(text=CLASSES_FIND)
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


def _skip_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text="Пропустить")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2)
    return kb


@router.message(F.text == BTN_CLASSES)
async def classes_menu(message: Message) -> None:
    await message.answer(
        "Рейтинг классов — выберите действие:",
        reply_markup=_classes_menu_kb().as_markup(resize_keyboard=True),
    )


@router.message(F.text == CLASSES_ADD)
async def class_add_start(message: Message, state: FSMContext) -> None:
    await state.set_state(ClassAddStates.phone)
    await message.answer("Введите телефон в формате 7XXXXXXXXXX:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ClassAddStates.phone)
async def class_add_phone(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await classes_menu(message)
        return
    phone = message.text.strip()
    if not (len(phone) == 11 and phone.startswith("7") and phone.isdigit()):
        await message.answer("Телефон должен быть в формате 7XXXXXXXXXX.")
        return
    await state.update_data(phone=phone)
    await state.set_state(ClassAddStates.tickets)
    await message.answer("Введите количество билетов:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ClassAddStates.tickets)
async def class_add_tickets(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await classes_menu(message)
        return
    try:
        tickets = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    await state.update_data(tickets_count=tickets)
    await state.set_state(ClassAddStates.cleanliness)
    await message.answer("Оценка чистоты (1-10):", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ClassAddStates.cleanliness)
async def class_add_cleanliness(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await classes_menu(message)
        return
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число от 1 до 10.")
        return
    if value < 1 or value > 10:
        await message.answer("Введите число от 1 до 10.")
        return
    await state.update_data(cleanliness_rating=value)
    await state.set_state(ClassAddStates.behavior)
    await message.answer("Оценка поведения (1-10):", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ClassAddStates.behavior)
async def class_add_behavior(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await classes_menu(message)
        return
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите число от 1 до 10.")
        return
    if value < 1 or value > 10:
        await message.answer("Введите число от 1 до 10.")
        return
    await state.update_data(behavior_rating=value)
    await state.set_state(ClassAddStates.school)
    await message.answer("Школа (или 'Пропустить'):", reply_markup=_skip_kb().as_markup(resize_keyboard=True))


@router.message(ClassAddStates.school)
async def class_add_school(message: Message, state: FSMContext) -> None:
    await _set_optional_field(message, state, "school", ClassAddStates.district, "Район (или 'Пропустить'):")


@router.message(ClassAddStates.district)
async def class_add_district(message: Message, state: FSMContext) -> None:
    await _set_optional_field(message, state, "district", ClassAddStates.session, "Сеанс (или 'Пропустить'):")


@router.message(ClassAddStates.session)
async def class_add_session(message: Message, state: FSMContext) -> None:
    await _set_optional_field(message, state, "session_info", ClassAddStates.rows, "Ряды (или 'Пропустить'):")


@router.message(ClassAddStates.rows)
async def class_add_rows(message: Message, state: FSMContext) -> None:
    await _set_optional_field(message, state, "seats_rows", ClassAddStates.info, "Доп. информация (или 'Пропустить'):")


@router.message(ClassAddStates.info)
async def class_add_info(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await classes_menu(message)
        return
    if message.text.strip().lower() == "пропустить":
        await state.update_data(extra_info=None)
    else:
        await state.update_data(extra_info=message.text.strip())
    await state.set_state(ClassAddStates.photo)
    kb = ReplyKeyboardBuilder()
    kb.button(text="Без фото")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2)
    await message.answer("Отправьте фото или нажмите 'Без фото':", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(ClassAddStates.photo, F.photo)
async def class_add_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    target = build_media_path("classes", data["phone"])
    await message.bot.download(message.photo[-1], destination=target)
    await _save_class_record(message, state, str(target))


@router.message(ClassAddStates.photo)
async def class_add_photo_text(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await classes_menu(message)
        return
    if message.text.strip() != "Без фото":
        await message.answer("Отправьте фото или нажмите 'Без фото'.")
        return
    await _save_class_record(message, state, None)


async def _save_class_record(message: Message, state: FSMContext, photo_path: Optional[str]) -> None:
    data = await state.get_data()
    payload = {
        "phone": data["phone"],
        "tickets_count": data["tickets_count"],
        "cleanliness_rating": data["cleanliness_rating"],
        "behavior_rating": data["behavior_rating"],
        "school": data.get("school"),
        "district": data.get("district"),
        "session_info": data.get("session_info"),
        "seats_rows": data.get("seats_rows"),
        "extra_info": data.get("extra_info"),
        "photo_path": photo_path,
        "created_at": now_iso(),
    }
    await classes.add_visit(payload)
    await state.clear()
    await message.answer("Запись сохранена.")
    await classes_menu(message)


async def _set_optional_field(
    message: Message,
    state: FSMContext,
    field: str,
    next_state: State,
    prompt: str,
) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await classes_menu(message)
        return
    if message.text.strip().lower() == "пропустить":
        await state.update_data(**{field: None})
    else:
        await state.update_data(**{field: message.text.strip()})
    await state.set_state(next_state)
    await message.answer(prompt, reply_markup=_skip_kb().as_markup(resize_keyboard=True))


@router.message(F.text == CLASSES_FIND)
async def class_find_start(message: Message, state: FSMContext) -> None:
    await state.set_state(ClassFindStates.phone_part)
    await message.answer("Введите часть телефона:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(ClassFindStates.phone_part)
async def class_find(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await classes_menu(message)
        return
    phone_part = message.text.strip()
    rows = await classes.find_by_phone(phone_part)
    await state.clear()
    if not rows:
        await message.answer("Ничего не найдено.")
        await classes_menu(message)
        return
    lines = [
        f"{r['phone']} | билеты={r['tickets_count']} | чистота={r['cleanliness_rating']} | "
        f"порядок={r['behavior_rating']} | {r.get('school') or '-'}"
        for r in rows
    ]
    await message.answer("\n".join(lines))
    await classes_menu(message)
