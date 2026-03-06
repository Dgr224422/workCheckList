from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.config import AppContext
from app.db import posters
from app.services.auth import ensure_min_role, get_role
from app.services.qr import decode_qr
from app.ui.labels import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_CERT,
    BTN_CHECKLISTS,
    BTN_CLASSES,
    BTN_FAQ,
    BTN_POPCORN,
    BTN_POSTERS,
    BTN_SCHEDULE,
    POSTERS_ADD,
    POSTERS_DELETE,
    POSTERS_FIND,
    POSTERS_HANG,
    POSTERS_TAKE_OFF,
    ROLE_MENU,
)
from app.utils.common import build_media_path, now_iso_moscow, today_moscow

router = Router()

QUICK_TAKE_OFF_REASON = "Фильм ушёл с проката"


class PosterAddStates(StatesGroup):
    title = State()
    release_date = State()
    poster_code = State()


class PosterFindStates(StatesGroup):
    query = State()


class PosterHangStates(StatesGroup):
    query = State()
    photo = State()


class PosterDeleteStates(StatesGroup):
    query = State()
    reason = State()


class PosterTakeOffStates(StatesGroup):
    query = State()
    reason = State()


def _posters_menu_kb(is_admin: bool) -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=POSTERS_ADD)
    kb.button(text=POSTERS_FIND)
    kb.button(text=POSTERS_HANG)
    if is_admin:
        kb.button(text=POSTERS_DELETE)
    kb.button(text=POSTERS_TAKE_OFF)
    kb.button(text=BTN_BACK)
    kb.button(text=BTN_CANCEL)
    kb.adjust(2, 2, 1, 2)
    return kb


def _cancel_back_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_BACK)
    kb.button(text=BTN_CANCEL)
    kb.adjust(2)
    return kb


def _take_off_reason_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=QUICK_TAKE_OFF_REASON)
    kb.button(text=BTN_BACK)
    kb.button(text=BTN_CANCEL)
    kb.adjust(1, 2)
    return kb


def _main_menu_kb(is_system_admin: bool) -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_CERT)
    kb.button(text=BTN_POPCORN)
    kb.button(text=BTN_CLASSES)
    kb.button(text=BTN_CHECKLISTS)
    kb.button(text=BTN_SCHEDULE)
    kb.button(text=BTN_FAQ)
    kb.button(text=BTN_POSTERS)
    if is_system_admin:
        kb.button(text=ROLE_MENU)
    kb.adjust(2, 2, 2, 1, 1)
    return kb


async def _to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    ctx: AppContext = message.bot.ctx
    role = await get_role(message.from_user.id, ctx)
    if role == "guest":
        await message.answer("Доступ ограничен.")
        return
    await message.answer(
        f"Роль: {role}. Выберите раздел.",
        reply_markup=_main_menu_kb(role == "system_admin").as_markup(resize_keyboard=True),
    )


def _parse_ddmmyyyy(value: str) -> Optional[str]:
    try:
        dt = datetime.strptime(value.strip(), "%d.%m.%Y")
    except ValueError:
        return None
    return dt.date().isoformat()


def _format_date(date_iso: str) -> str:
    try:
        return datetime.strptime(date_iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return date_iso


def _days_to_release(date_iso: str) -> int:
    release = datetime.strptime(date_iso, "%Y-%m-%d").date()
    return (release - today_moscow()).days


def _poster_line(row: dict[str, Any]) -> str:
    days = _days_to_release(row["release_date"])
    if days > 0:
        rel_text = f"до выхода {days} дн."
    elif days == 0:
        rel_text = "выходит сегодня"
    else:
        rel_text = f"вышел {-days} дн. назад"

    status = "повешен" if row.get("is_hung") else "не повешен"
    taken_off = "снят" if row.get("is_taken_off") else "не снят"
    return (
        f"{row['title']} | код: {row['poster_code']} | релиз: {_format_date(row['release_date'])}\n"
        f"Приехал: {row['arrived_at']}\n"
        f"Статус: {status}, {taken_off}, {rel_text}"
    )


async def _send_poster_details(message: Message, row: dict[str, Any]) -> None:
    await message.answer(_poster_line(row))
    photo_path = row.get("hung_photo_path")
    if row.get("is_hung") and not row.get("is_taken_off") and photo_path and Path(photo_path).exists():
        await message.answer("Постер повешен. Фото места:")
        await message.answer_photo(FSInputFile(photo_path))


async def _send_candidate_buttons(message: Message, mode: str, rows: list[dict[str, Any]]) -> None:
    kb = InlineKeyboardBuilder()
    for row in rows[:5]:
        kb.button(
            text=f"{row['poster_code']} | {row['title'][:26]}",
            callback_data=f"poster_pick:{mode}:{row['id']}",
        )
    kb.adjust(1)
    await message.answer(
        "Найдено несколько вариантов. Выберите один из кнопок ниже:",
        reply_markup=kb.as_markup(),
    )


async def _resolve_query(message: Message, query: str, mode: str) -> Optional[dict[str, Any]]:
    date_iso = _parse_ddmmyyyy(query)
    if date_iso:
        rows = await posters.search_by_release_date(date_iso)
        if not rows:
            await message.answer("По этой дате релиза ничего не найдено.")
            return None
        if mode == "find":
            for row in rows:
                full = await posters.get_poster_by_id(row["id"])
                if full:
                    await _send_poster_details(message, full)
            return None
        if len(rows) == 1:
            return await posters.get_poster_by_id(rows[0]["id"])
        await _send_candidate_buttons(message, mode, rows)
        return None

    exact = await posters.get_active_by_code(query.strip())
    if exact:
        return exact

    rows = await posters.search_candidates(query)
    if not rows:
        await message.answer("Совпадений не найдено. Уточните название/код или отправьте фото со штрихкодом.")
        return None
    if len(rows) == 1:
        return await posters.get_poster_by_id(rows[0]["id"])
    await _send_candidate_buttons(message, mode, rows)
    return None


async def _resolve_from_photo(message: Message, mode: str) -> Optional[dict[str, Any]]:
    target = build_media_path("posters_scan", str(message.from_user.id))
    await message.bot.download(message.photo[-1], destination=target)
    decoded = decode_qr(str(target))
    try:
        target.unlink(missing_ok=True)
    except Exception:
        pass

    if not decoded:
        await message.answer("Не удалось распознать штрихкод. Отправьте более чёткое фото или введите код вручную.")
        return None
    await message.answer(f"Распознан код: {decoded}")
    return await _resolve_query(message, decoded, mode)


@router.message(F.text == BTN_POSTERS)
async def posters_menu(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    is_admin = await ensure_min_role(message.from_user.id, "admin", ctx)
    await message.answer(
        "Постеры — выберите действие:",
        reply_markup=_posters_menu_kb(is_admin).as_markup(resize_keyboard=True),
    )


@router.message(F.text == POSTERS_ADD)
async def poster_add_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.clear()
    await state.set_state(PosterAddStates.title)
    await message.answer("Добавление постера. Введите название фильма/сеанса:", reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True))


@router.message(PosterAddStates.title)
async def poster_add_title(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.clear()
        await posters_menu(message)
        return
    await state.update_data(title=text)
    await state.set_state(PosterAddStates.release_date)
    await message.answer("Введите дату выхода в формате ДД.ММ.ГГГГ:", reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True))


@router.message(PosterAddStates.release_date)
async def poster_add_release_date(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.set_state(PosterAddStates.title)
        await message.answer("Введите название фильма/сеанса:", reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True))
        return

    date_iso = _parse_ddmmyyyy(text)
    if not date_iso:
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ.")
        return
    await state.update_data(release_date=date_iso)
    await state.set_state(PosterAddStates.poster_code)
    await message.answer("Введите код постера (или штрихкод):", reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True))


@router.message(PosterAddStates.poster_code)
async def poster_add_code(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.set_state(PosterAddStates.release_date)
        await message.answer("Введите дату выхода в формате ДД.ММ.ГГГГ:", reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True))
        return

    if not text:
        await message.answer("Код не должен быть пустым.")
        return

    data = await state.get_data()
    created_at = now_iso_moscow()
    ok = await posters.add_poster(
        {
            "title": data["title"],
            "release_date": data["release_date"],
            "poster_code": text,
            "barcode_code": text,
            "arrived_at": created_at,
            "arrived_by": message.from_user.id,
            "created_at": created_at,
        }
    )
    await state.clear()
    if not ok:
        await message.answer("Не удалось добавить постер: код уже существует или ошибка БД.")
    else:
        await message.answer(
            "Постер добавлен:\n"
            f"Название: {data['title']}\n"
            f"Дата выхода: {_format_date(data['release_date'])}\n"
            f"Код: {text}"
        )
    await posters_menu(message)


@router.message(F.text == POSTERS_FIND)
async def poster_find_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.clear()
    await state.set_state(PosterFindStates.query)
    await message.answer(
        "Найти постер: введите название, код, дату выхода (ДД.ММ.ГГГГ) или отправьте фото штрихкода.",
        reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
    )


@router.message(PosterFindStates.query, F.photo)
async def poster_find_photo(message: Message, state: FSMContext) -> None:
    row = await _resolve_from_photo(message, "find")
    if row:
        await _send_poster_details(message, row)


@router.message(PosterFindStates.query)
async def poster_find_query(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.clear()
        await posters_menu(message)
        return

    row = await _resolve_query(message, text, "find")
    if row:
        await _send_poster_details(message, row)


@router.message(F.text == POSTERS_HANG)
async def poster_hang_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.clear()
    await state.set_state(PosterHangStates.query)
    await message.answer(
        "Повесить постер: введите название/код или отправьте фото штрихкода.",
        reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
    )


@router.message(PosterHangStates.query, F.photo)
async def poster_hang_query_photo(message: Message, state: FSMContext) -> None:
    row = await _resolve_from_photo(message, "hang")
    if row:
        await _start_hang_photo_step(message, state, row)


@router.message(PosterHangStates.query)
async def poster_hang_query(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.clear()
        await posters_menu(message)
        return

    row = await _resolve_query(message, text, "hang")
    if row:
        await _start_hang_photo_step(message, state, row)


async def _start_hang_photo_step(message: Message, state: FSMContext, row: dict[str, Any]) -> None:
    if row.get("status") != "active":
        await message.answer("Постер неактивен.")
        return
    if row.get("is_hung"):
        await message.answer("Этот постер уже отмечен как повешенный.")
        return
    await state.update_data(selected_poster_id=row["id"])
    await state.set_state(PosterHangStates.photo)
    await message.answer(
        f"Найден постер: {row['title']} ({row['poster_code']}).\n"
        "Отправьте фото места, где он висит.",
        reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
    )


@router.message(PosterHangStates.photo, F.photo)
async def poster_hang_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    poster_id = data.get("selected_poster_id")
    if not poster_id:
        await state.set_state(PosterHangStates.query)
        await message.answer("Сначала выберите постер.")
        return

    row = await posters.get_poster_by_id(int(poster_id))
    if not row:
        await state.set_state(PosterHangStates.query)
        await message.answer("Постер не найден.")
        return

    target = build_media_path("posters", row["poster_code"])
    await message.bot.download(message.photo[-1], destination=target)
    ok = await posters.mark_hung(
        row["id"],
        message.from_user.id,
        now_iso_moscow(),
        str(target),
    )
    await state.clear()
    if not ok:
        await message.answer("Не удалось отметить постер как повешенный (возможно, уже отмечен).")
    else:
        await message.answer("Постер отмечен как повешенный, фото сохранено.")
    await posters_menu(message)


@router.message(PosterHangStates.photo)
async def poster_hang_photo_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.update_data(selected_poster_id=None)
        await state.set_state(PosterHangStates.query)
        await message.answer(
            "Введите название/код постера или отправьте фото штрихкода.",
            reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
        )
        return
    await message.answer("Отправьте фото места, где висит постер.")


@router.message(F.text == POSTERS_DELETE)
async def poster_delete_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.clear()
    await state.set_state(PosterDeleteStates.query)
    await message.answer(
        "Удалить постер: введите название/код или отправьте фото штрихкода.",
        reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
    )


@router.message(PosterDeleteStates.query, F.photo)
async def poster_delete_query_photo(message: Message, state: FSMContext) -> None:
    row = await _resolve_from_photo(message, "delete")
    if row:
        await _start_delete_reason_step(message, state, row)


@router.message(PosterDeleteStates.query)
async def poster_delete_query(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.clear()
        await posters_menu(message)
        return

    row = await _resolve_query(message, text, "delete")
    if row:
        await _start_delete_reason_step(message, state, row)


async def _start_delete_reason_step(message: Message, state: FSMContext, row: dict[str, Any]) -> None:
    await state.update_data(selected_poster_id=row["id"])
    await state.set_state(PosterDeleteStates.reason)
    await message.answer(
        f"Найден постер: {row['title']} ({row['poster_code']}).\nВведите причину удаления:",
        reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
    )


@router.message(PosterDeleteStates.reason)
async def poster_delete_reason(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.update_data(selected_poster_id=None)
        await state.set_state(PosterDeleteStates.query)
        await message.answer(
            "Введите название/код постера или отправьте фото штрихкода.",
            reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
        )
        return
    if not text:
        await message.answer("Причина удаления обязательна.")
        return

    data = await state.get_data()
    poster_id = data.get("selected_poster_id")
    if not poster_id:
        await state.set_state(PosterDeleteStates.query)
        await message.answer("Сначала выберите постер.")
        return

    row = await posters.get_poster_by_id(int(poster_id))
    if not row:
        await state.clear()
        await message.answer("Постер не найден.")
        await posters_menu(message)
        return

    deleted_at = now_iso_moscow()
    ok = await posters.soft_delete(row["id"], message.from_user.id, deleted_at, text, keep_days=365)
    await state.clear()
    if not ok:
        await message.answer("Не удалось удалить постер (возможно, он уже удалён).")
        await posters_menu(message)
        return

    await message.answer("Постер удалён из активной базы. Архив будет храниться 365 дней.")
    ctx: AppContext = message.bot.ctx
    try:
        await message.bot.send_message(
            ctx.settings.system_admin_id,
            "Удаление постера:\n"
            f"Название: {row['title']}\n"
            f"Код: {row['poster_code']}\n"
            f"Причина: {text}\n"
            f"Удалил: {message.from_user.id}\n"
            f"Время: {deleted_at}",
        )
    except Exception:
        pass
    await posters_menu(message)


@router.message(F.text == POSTERS_TAKE_OFF)
async def poster_take_off_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.clear()
    await state.set_state(PosterTakeOffStates.query)
    await message.answer(
        "Снять постер: введите название/код или отправьте фото штрихкода.",
        reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
    )


@router.message(PosterTakeOffStates.query, F.photo)
async def poster_take_off_query_photo(message: Message, state: FSMContext) -> None:
    row = await _resolve_from_photo(message, "takeoff")
    if row:
        await _start_take_off_reason_step(message, state, row)


@router.message(PosterTakeOffStates.query)
async def poster_take_off_query(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.clear()
        await posters_menu(message)
        return

    row = await _resolve_query(message, text, "takeoff")
    if row:
        await _start_take_off_reason_step(message, state, row)


async def _start_take_off_reason_step(message: Message, state: FSMContext, row: dict[str, Any]) -> None:
    if not row.get("is_hung"):
        await message.answer("Постер ещё не отмечен как повешенный. Сначала используйте пункт 'Повесить постер'.")
        return
    if row.get("is_taken_off"):
        await message.answer("Этот постер уже отмечен как снятый.")
        return

    await state.update_data(selected_poster_id=row["id"])
    await state.set_state(PosterTakeOffStates.reason)
    await message.answer(
        f"Найден постер: {row['title']} ({row['poster_code']}).\nУкажите причину снятия:",
        reply_markup=_take_off_reason_kb().as_markup(resize_keyboard=True),
    )


@router.message(PosterTakeOffStates.reason)
async def poster_take_off_reason(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == BTN_CANCEL:
        await _to_main_menu(message, state)
        return
    if text == BTN_BACK:
        await state.update_data(selected_poster_id=None)
        await state.set_state(PosterTakeOffStates.query)
        await message.answer(
            "Введите название/код постера или отправьте фото штрихкода.",
            reply_markup=_cancel_back_kb().as_markup(resize_keyboard=True),
        )
        return
    if not text:
        await message.answer("Причина снятия обязательна.")
        return

    data = await state.get_data()
    poster_id = data.get("selected_poster_id")
    if not poster_id:
        await state.set_state(PosterTakeOffStates.query)
        await message.answer("Сначала выберите постер.")
        return

    ok = await posters.mark_taken_off(
        int(poster_id),
        message.from_user.id,
        now_iso_moscow(),
        text,
    )
    await state.clear()
    if not ok:
        await message.answer("Не удалось отметить постер как снятый (возможно, он уже снят).")
    else:
        await message.answer("Постер отмечен как снятый.")
    await posters_menu(message)


@router.callback_query(F.data.startswith("poster_pick:"))
async def poster_pick(call: CallbackQuery, state: FSMContext) -> None:
    parts = (call.data or "").split(":", maxsplit=2)
    if len(parts) != 3:
        await call.answer()
        return
    mode, poster_id_raw = parts[1], parts[2]
    try:
        poster_id = int(poster_id_raw)
    except ValueError:
        await call.answer("Некорректный ID", show_alert=True)
        return

    row = await posters.get_poster_by_id(poster_id)
    if not row:
        await call.answer("Постер не найден", show_alert=True)
        return

    if mode == "find":
        await _send_poster_details(call.message, row)
        await call.answer("Показал карточку")
        return

    if mode == "hang":
        await _start_hang_photo_step(call.message, state, row)
        await call.answer("Выбран")
        return

    if mode == "delete":
        await _start_delete_reason_step(call.message, state, row)
        await call.answer("Выбран")
        return

    if mode == "takeoff":
        await _start_take_off_reason_step(call.message, state, row)
        await call.answer("Выбран")
        return

    await call.answer()
