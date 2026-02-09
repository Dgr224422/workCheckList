import logging
import shlex

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import AppContext
from app.db import certificates
from app.services.auth import ensure_min_role
from app.services.qr import decode_qr
from app.utils.common import build_media_path, now_iso

router = Router()

ISSUE_REASONS = [
    "Возврат/извинение",
    "Технический сбой",
    "Акция",
    "День рождения",
    "Другое",
]

_PENDING_ISSUE: dict[int, dict] = {}


@router.message(F.text == "🎟 Сертификаты")
async def certificates_menu(message: Message) -> None:
    await message.answer(
        "Сертификаты:\n"
        "• /cert_issue — пошаговая выдача сертификата (admin)\n"
        "• /cert_find PART\n"
        "• /cert_filter reason=\"Технический сбой\" date_from=YYYY-MM-DD date_to=YYYY-MM-DD\n"
        "• Отправьте фото QR с подписью cert_qr\n"
        "• /cert_redeem CODE SESSION ROW SEATS"
    )


@router.message(F.text == "/cert_issue")
async def cert_issue_start(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return

    _PENDING_ISSUE[message.from_user.id] = {}
    await message.answer("Введите ФИО/идентификатор клиента для сертификата:")


@router.message(F.text.in_({"2", "4"}))
async def cert_issue_tickets(message: Message) -> None:
    state = _PENDING_ISSUE.get(message.from_user.id)
    if not state or "owner_name" not in state:
        return

    state["tickets_count"] = int(message.text)
    buttons = [
        [InlineKeyboardButton(text=reason, callback_data=f"cert_reason:{reason}")]
        for reason in ISSUE_REASONS
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выберите причину выдачи сертификата:", reply_markup=kb)


@router.callback_query(F.data.startswith("cert_reason:"))
async def cert_issue_reason(call: CallbackQuery) -> None:
    reason = call.data.split(":", maxsplit=1)[1]
    state = _PENDING_ISSUE.get(call.from_user.id)
    if not state:
        await call.answer("Сначала /cert_issue", show_alert=True)
        return

    if reason == "Другое":
        state["awaiting_custom_reason"] = True
        await call.message.answer("Введите свою причину выдачи сертификата:")
        await call.answer()
        return

    state["issue_reason"] = reason
    await _finalize_issue(call.message, call.from_user.id)
    await call.answer()


@router.message(F.text)
async def cert_issue_text_steps(message: Message) -> None:
    state = _PENDING_ISSUE.get(message.from_user.id)
    if not state:
        return

    if "owner_name" not in state:
        state["owner_name"] = message.text.strip()
        await message.answer("Укажите количество билетов для сертификата (только 2 или 4):\nОтправьте 2 или 4")
        return

    if state.get("awaiting_custom_reason"):
        state["issue_reason"] = message.text.strip()
        state.pop("awaiting_custom_reason", None)
        await _finalize_issue(message, message.from_user.id)


async def _finalize_issue(message: Message, user_id: int) -> None:
    state = _PENDING_ISSUE.get(user_id)
    if not state:
        return
    if "owner_name" not in state or "tickets_count" not in state or "issue_reason" not in state:
        return

    code = await certificates.generate_unique_code()
    await certificates.add_certificate(
        code=code,
        tickets_count=state["tickets_count"],
        owner_name=state["owner_name"],
        issue_reason=state["issue_reason"],
        created_at=now_iso(),
    )

    _PENDING_ISSUE.pop(user_id, None)
    await message.answer(
        "Сертификат создан:\n"
        f"Код: {code}\n"
        f"Билетов: {state['tickets_count']}\n"
        f"Причина: {state['issue_reason']}\n"
        f"Получатель: {state['owner_name']}"
    )


@router.message(F.text.startswith("/cert_find "))
async def cert_find(message: Message) -> None:
    code_part = message.text.removeprefix("/cert_find ").strip()
    rows = await certificates.find_by_code_part(code_part)
    if not rows:
        await message.answer("Совпадений не найдено")
        return

    lines = []
    for row in rows:
        lines.append(
            f"{row['code']} | билетов={row['tickets_count']} | {row['status']} | {row['issue_reason']} | выдан: {row['created_at']}"
        )
    await message.answer("\n".join(lines))


@router.message(F.text.startswith("/cert_filter "))
async def cert_filter(message: Message) -> None:
    query = message.text.removeprefix("/cert_filter ").strip()
    try:
        tokens = shlex.split(query)
    except ValueError:
        await message.answer('Неверный формат. Пример: /cert_filter reason=\"Технический сбой\" date_from=2026-01-01 date_to=2026-01-31')
        return

    params: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            continue
        k, v = token.split("=", maxsplit=1)
        params[k.strip()] = v.strip()

    rows = await certificates.filter_certificates(
        reason=params.get("reason"),
        date_from=params.get("date_from"),
        date_to=params.get("date_to"),
    )
    if not rows:
        await message.answer("По фильтру ничего не найдено")
        return

    lines = []
    for r in rows:
        lines.append(
            f"{r['code']} | {r['issue_reason']} | выдан {r['created_at']} | "
            f"погашен {r['redeemed_at'] or '-'} | сеанс {r['redeemed_session'] or '-'} | "
            f"ряд {r['redeemed_row'] or '-'} | места {r['redeemed_seats'] or '-'}"
        )
    await message.answer("\n".join(lines[:30]))


@router.message(F.text.startswith("/cert_redeem "))
async def cert_redeem(message: Message) -> None:
    parts = message.text.split(maxsplit=4)
    if len(parts) < 5:
        await message.answer("Формат: /cert_redeem CODE SESSION ROW SEATS")
        return

    code = parts[1].strip()
    session = parts[2].strip()
    row = parts[3].strip()
    seats = parts[4].strip()

    changed = await certificates.redeem(code, now_iso(), session, row, seats)
    await message.answer("Погашено" if changed else "Не найден активный сертификат")


@router.message(F.photo)
async def cert_qr_photo(message: Message) -> None:
    if not message.caption or "cert_qr" not in message.caption:
        return

    photo = message.photo[-1]
    target = build_media_path("certificates", f"qr_{message.from_user.id}")
    await message.bot.download(photo, destination=target)

    code = decode_qr(str(target))
    if not code:
        await message.answer("QR не распознан")
        return

    row = await certificates.get_by_code(code)
    if not row:
        await message.answer(f"QR прочитан: {code}. Сертификат не найден")
        return

    logging.info("Certificate qr resolved code=%s by user=%s", code, message.from_user.id)
    await message.answer(
        f"Найден: {row['code']} | билетов={row['tickets_count']} | {row['status']} | "
        f"причина: {row['issue_reason']} | выдан: {row['created_at']}"
    )
