import logging

from aiogram import F, Router
from aiogram.types import Message

from app.config import AppContext
from app.db import certificates
from app.services.auth import ensure_min_role
from app.services.qr import decode_qr
from app.utils.common import build_media_path, now_iso

router = Router()


@router.message(F.text == "🎟 Сертификаты")
async def certificates_menu(message: Message) -> None:
    await message.answer(
        "Сертификаты:\n"
        "• /cert_add CODE AMOUNT OWNER (admin)\n"
        "• /cert_find PART\n"
        "• Отправьте фото QR с подписью cert_qr\n"
        "• /cert_redeem CODE (admin)"
    )


@router.message(F.text.startswith("/cert_add "))
async def cert_add(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return

    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Формат: /cert_add CODE AMOUNT OWNER")
        return

    code = parts[1].strip()
    if len(code) < 4:
        await message.answer("Код слишком короткий")
        return
    amount = int(parts[2])
    owner_name = parts[3].strip() if len(parts) > 3 else None
    await certificates.add_certificate(code=code, amount=amount, owner_name=owner_name, created_at=now_iso())
    await message.answer(f"Сертификат {code} добавлен")


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
            f"{row['code']} | {row['amount']}₽ | {row['status']} | {row.get('owner_name') or '-'}"
        )
    await message.answer("\n".join(lines))


@router.message(F.text.startswith("/cert_redeem "))
async def cert_redeem(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return

    code = message.text.removeprefix("/cert_redeem ").strip()
    changed = await certificates.redeem(code, now_iso())
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
        f"Найден: {row['code']} | {row['amount']}₽ | {row['status']} | владелец: {row.get('owner_name') or '-'}"
    )
