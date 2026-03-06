import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.config import AppContext
from app.db import certificates
from app.services.auth import ensure_min_role
from app.services.qr import decode_qr
from app.ui.labels import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_CERT,
    CERT_CREATE_STOCK,
    CERT_FILTER,
    CERT_FIND,
    CERT_ISSUE,
    CERT_QR,
    CERT_REDEEM,
    CERT_STATS,
)
from app.utils.common import build_media_path, now_iso

router = Router()

ISSUE_REASONS = [
    "Возврат/извинение",
    "Технический сбой",
    "Акция",
    "День рождения",
    "Другое",
]


class CertIssueStates(StatesGroup):
    tickets_count = State()
    owner_name = State()
    reason = State()
    custom_reason = State()
    code = State()


class CertFindStates(StatesGroup):
    code_part = State()


class CertFilterStates(StatesGroup):
    reason = State()
    custom_reason = State()
    date_from = State()
    date_to = State()


class CertRedeemStates(StatesGroup):
    code = State()
    session = State()
    row = State()
    seats = State()


class CertQrStates(StatesGroup):
    photo = State()
    awaiting = State()


class CertCreateStockStates(StatesGroup):
    tickets_count = State()
    quantity = State()


def _cert_menu_kb(is_admin: bool) -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    if is_admin:
        kb.button(text=CERT_CREATE_STOCK)
        kb.button(text=CERT_ISSUE)
        kb.button(text=CERT_REDEEM)
        kb.button(text=CERT_STATS)
    kb.button(text=CERT_FIND)
    kb.button(text=CERT_FILTER)
    kb.button(text=CERT_QR)
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


def _skip_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text="Пропустить")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2)
    return kb


def _is_skip(text: str) -> bool:
    return text.strip().lower() in {"пропустить", "skip"}

@router.message(F.text == BTN_CERT)
async def certificates_menu(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    is_admin = await ensure_min_role(message.from_user.id, "admin", ctx)
    await message.answer(
        "Сертификаты — выберите действие:",
        reply_markup=_cert_menu_kb(is_admin).as_markup(resize_keyboard=True),
    )


@router.message(F.text == CERT_ISSUE)
async def cert_issue_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(CertIssueStates.tickets_count)
    kb = ReplyKeyboardBuilder()
    kb.button(text="2")
    kb.button(text="4")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2, 1)
    await message.answer("Сколько билетов у сертификата? Выберите 2 или 4:", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(CertIssueStates.tickets_count)
async def cert_issue_tickets(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    if message.text not in {"2", "4"}:
        await message.answer("Выберите 2 или 4.")
        return
    await state.update_data(tickets_count=int(message.text))
    available = await certificates.get_available(int(message.text))
    if not available:
        await message.answer("Нет заготовок с таким количеством билетов. Сначала создайте заготовки.")
        await state.clear()
        await certificates_menu(message)
        return
    await state.update_data(code=available["code"])
    await state.set_state(CertIssueStates.owner_name)
    await message.answer(f"Доступна заготовка с кодом {available['code']}. Введите ФИО/идентификатор клиента:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(F.text == CERT_CREATE_STOCK)
async def cert_create_stock_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(CertCreateStockStates.tickets_count)
    kb = ReplyKeyboardBuilder()
    kb.button(text="2")
    kb.button(text="4")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2, 1)
    await message.answer("Для заготовок выберите количество билетов (2 или 4):", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(CertCreateStockStates.tickets_count)
async def cert_create_stock_tickets(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    if message.text not in {"2", "4"}:
        await message.answer("Выберите 2 или 4.")
        return
    await state.update_data(tickets_count=int(message.text))
    await state.set_state(CertCreateStockStates.quantity)
    await message.answer("Сколько заготовок создать? Введите число:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(CertCreateStockStates.quantity)
async def cert_create_stock_quantity(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    try:
        qty = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    if qty <= 0 or qty > 200:
        await message.answer("Введите число от 1 до 200.")
        return
    data = await state.get_data()
    codes = await certificates.create_batch(qty, data["tickets_count"], now_iso())
    await state.clear()
    codes_text = ", ".join(codes[:20])
    suffix = "..." if len(codes) > 20 else ""
    await message.answer(
        f"Создано {len(codes)} заготовок на {data['tickets_count']} билетов.\nКоды: {codes_text}{suffix}"
    )
    await certificates_menu(message)


@router.message(F.text == CERT_STATS)
async def cert_stats(message: Message) -> None:
    stats = await certificates.stats()
    def fmt(status: str) -> str:
        counts = stats.get(status, {}) or {}
        parts = [f"{k}б: {v}" for k, v in sorted(counts.items())]
        total = sum(counts.values())
        return f"{status}: {total}" + (f" ({', '.join(parts)})" if parts else "")
    text = "\n".join([fmt("stock"), fmt("active"), fmt("redeemed")])
    await message.answer("Статистика сертификатов:\n" + text)


@router.message(CertIssueStates.owner_name)
async def cert_issue_owner(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    await state.update_data(owner_name=message.text.strip())
    await state.set_state(CertIssueStates.reason)
    buttons = [
        [InlineKeyboardButton(text=reason, callback_data=f"cert_reason:{reason}")]
        for reason in ISSUE_REASONS
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите причину выдачи:", reply_markup=kb)


@router.callback_query(F.data.startswith("cert_reason:"))
async def cert_issue_reason(call: CallbackQuery, state: FSMContext) -> None:
    reason = call.data.split(":", maxsplit=1)[1]
    if reason == "Другое":
        await state.set_state(CertIssueStates.custom_reason)
        await call.message.answer("Введите свою причину:")
        await call.answer()
        return

    await state.update_data(issue_reason=reason)
    await _finalize_issue(call.message, state)
    await call.answer()


@router.message(CertIssueStates.custom_reason)
async def cert_issue_custom_reason(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    await state.update_data(issue_reason=message.text.strip())
    await _finalize_issue(message, state)


async def _finalize_issue(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if "owner_name" not in data or "tickets_count" not in data or "issue_reason" not in data or "code" not in data:
        await message.answer("Недостаточно данных для выдачи.")
        return
    issued = await certificates.issue_certificate(
        data["code"],
        data["owner_name"],
        data["issue_reason"],
        now_iso(),
    )
    if not issued:
        await message.answer("Не удалось выдать: заготовка уже занята или отсутствует.")
        await state.clear()
        await certificates_menu(message)
        return
    await state.clear()
    await message.answer(
        "Сертификат создан:\n"
        f"Код: {data['code']}\n"
        f"Билетов: {data['tickets_count']}\n"
        f"Причина: {data['issue_reason']}\n"
        f"Получатель: {data['owner_name']}"
    )
    await certificates_menu(message)


@router.message(F.text == CERT_FIND)
async def cert_find_start(message: Message, state: FSMContext) -> None:
    await state.set_state(CertFindStates.code_part)
    await message.answer("Введите часть кода для поиска:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(CertFindStates.code_part)
async def cert_find_run(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    rows = await certificates.find_by_code_part(message.text.strip())
    await state.clear()
    if not rows:
        await message.answer("Совпадений не найдено.")
        await certificates_menu(message)
        return
    lines = [
        f"{row['code']} | билетов={row['tickets_count']} | {row['status']} | "
        f"{row.get('issue_reason') or '-'} | выдан: {row.get('issued_at') or '-'}"
        for row in rows
    ]
    await message.answer("\n".join(lines))
    await certificates_menu(message)


@router.message(F.text == CERT_FILTER)
async def cert_filter_start(message: Message, state: FSMContext) -> None:
    await state.set_state(CertFilterStates.reason)
    buttons = [
        [InlineKeyboardButton(text=reason, callback_data=f"cert_filter_reason:{reason}")]
        for reason in ISSUE_REASONS
    ]
    buttons.append([InlineKeyboardButton(text="Пропустить", callback_data="cert_filter_reason:skip")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите причину или пропустите:", reply_markup=kb)


@router.callback_query(F.data.startswith("cert_filter_reason:"))
async def cert_filter_reason(call: CallbackQuery, state: FSMContext) -> None:
    reason = call.data.split(":", maxsplit=1)[1]
    if reason == "skip":
        await state.update_data(reason=None)
        await state.set_state(CertFilterStates.date_from)
        await call.message.answer(
            "Введите дату от (YYYY-MM-DD) или нажмите 'Пропустить':",
            reply_markup=_skip_kb().as_markup(resize_keyboard=True),
        )
        await call.answer()
        return
    if reason == "Другое":
        await state.set_state(CertFilterStates.custom_reason)
        await call.message.answer("Введите свою причину:")
        await call.answer()
        return
    await state.update_data(reason=reason)
    await state.set_state(CertFilterStates.date_from)
    await call.message.answer(
        "Введите дату от (YYYY-MM-DD) или нажмите 'Пропустить':",
        reply_markup=_skip_kb().as_markup(resize_keyboard=True),
    )
    await call.answer()


@router.message(CertFilterStates.custom_reason)
async def cert_filter_custom_reason(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    await state.update_data(reason=message.text.strip())
    await state.set_state(CertFilterStates.date_from)
    await message.answer(
        "Введите дату от (YYYY-MM-DD) или нажмите 'Пропустить':",
        reply_markup=_skip_kb().as_markup(resize_keyboard=True),
    )


@router.message(CertFilterStates.date_from)
async def cert_filter_date_from(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    text = message.text.strip()
    await state.update_data(date_from=None if _is_skip(text) else text)
    await state.set_state(CertFilterStates.date_to)
    await message.answer(
        "Введите дату до (YYYY-MM-DD) или нажмите 'Пропустить':",
        reply_markup=_skip_kb().as_markup(resize_keyboard=True),
    )


@router.message(CertFilterStates.date_to)
async def cert_filter_date_to(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    text = message.text.strip()
    data = await state.get_data()
    rows = await certificates.filter_certificates(
        reason=data.get("reason"),
        date_from=data.get("date_from"),
        date_to=None if _is_skip(text) else text,
    )
    await state.clear()
    if not rows:
        await message.answer("По фильтру ничего не найдено.")
        await certificates_menu(message)
        return
    lines = [
        f"{r['code']} | {r.get('issue_reason') or '-'} | выдан {r.get('issued_at') or '-'} | "
        f"погашен {r['redeemed_at'] or '-'} | сеанс {r['redeemed_session'] or '-'} | "
        f"ряд {r['redeemed_row'] or '-'} | места {r['redeemed_seats'] or '-'}"
        for r in rows
    ]
    await message.answer("\n".join(lines[:30]))
    await certificates_menu(message)


@router.message(F.text == CERT_REDEEM)
async def cert_redeem_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(CertRedeemStates.code)
    await message.answer(
        "Введите код сертификата или отправьте фото QR-кода:",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


@router.message(CertRedeemStates.code, F.photo)
async def cert_redeem_qr(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    target = build_media_path("certificates", f"redeem_qr_{message.from_user.id}")
    await message.bot.download(photo, destination=target)

    code = decode_qr(str(target))
    if not code:
        await message.answer("QR не распознан. Отправьте другое фото или введите код вручную.")
        return

    row = await certificates.get_by_code(code)
    if not row:
        await message.answer("Сертификат не найден. Отправьте другое фото или введите код вручную.")
        return
    status = row["status"]
    if status != "active":
        await message.answer(f"Сертификат найден, но статус = {status}. Погашение невозможно.")
        return

    await state.update_data(code=code)
    await state.set_state(CertRedeemStates.session)
    await message.answer(f"Код распознан: {code}\nВведите сеанс:")


@router.message(CertRedeemStates.code)
async def cert_redeem_code(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    await state.update_data(code=message.text.strip())
    await state.set_state(CertRedeemStates.session)
    await message.answer("Введите сеанс:")


@router.message(CertRedeemStates.session)
async def cert_redeem_session(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    await state.update_data(session=message.text.strip())
    await state.set_state(CertRedeemStates.row)
    await message.answer("Введите ряд:")


@router.message(CertRedeemStates.row)
async def cert_redeem_row(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    await state.update_data(row=message.text.strip())
    await state.set_state(CertRedeemStates.seats)
    await message.answer("Введите места (например 5,6):")


@router.message(CertRedeemStates.seats)
async def cert_redeem_seats(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    data = await state.get_data()
    changed = await certificates.redeem(
        data["code"],
        now_iso(),
        data["session"],
        data["row"],
        message.text.strip(),
    )
    await state.clear()
    await message.answer("Погашено" if changed else "Не найден активный сертификат.")
    await certificates_menu(message)


@router.message(F.text == CERT_QR)
async def cert_qr_start(message: Message, state: FSMContext) -> None:
    await state.set_state(CertQrStates.photo)
    await message.answer("Отправьте фото QR-кода сертификата:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(CertQrStates.photo, F.photo)
async def cert_qr_photo(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1]
    target = build_media_path("certificates", f"qr_{message.from_user.id}")
    await message.bot.download(photo, destination=target)

    code = decode_qr(str(target))
    if not code:
        await message.answer("QR не распознан.")
        return

    row = await certificates.get_by_code(code)
    await state.clear()
    if not row:
        await message.answer(f"QR прочитан: {code}. Сертификат не найден.")
        await certificates_menu(message)
        return

    logging.info("Certificate qr resolved code=%s by user=%s", code, message.from_user.id)
    status = row["status"]
    info = (
        f"Найден: {row['code']} | билетов={row['tickets_count']} | статус={status} | "
        f"причина: {row.get('issue_reason') or '-'} | выдан: {row.get('issued_at') or '-'}"
    )
    await message.answer(info)
    await certificates_menu(message)


@router.message(CertQrStates.photo)
async def cert_qr_photo_missing(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await certificates_menu(message)
        return
    await message.answer("Нужно отправить фото QR-кода.")
