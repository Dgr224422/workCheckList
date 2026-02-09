from aiogram import F, Router
from aiogram.types import Message

from app.db import classes
from app.utils.common import build_media_path, now_iso

router = Router()
_PENDING: dict[int, dict] = {}


@router.message(F.text == "🏫 Рейтинг классов")
async def classes_menu(message: Message) -> None:
    await message.answer(
        "Классы:\n"
        "/class_add PHONE TICKETS CLEANLINESS(1-10) BEHAVIOR(1-10) SCHOOL|DISTRICT|SESSION|ROWS|INFO\n"
        "Затем (опционально) отправьте фото с подписью class_photo"
    )


@router.message(F.text.startswith("/class_add "))
async def class_add(message: Message) -> None:
    text = message.text.removeprefix("/class_add ").strip()
    base, *rest = text.split(maxsplit=5)
    parts = text.split(maxsplit=5)
    if len(parts) < 5:
        await message.answer("Недостаточно полей")
        return

    phone = parts[0]
    if not (len(phone) == 11 and phone.startswith("7") and phone.isdigit()):
        await message.answer("Телефон должен быть в формате 79781232121")
        return

    tickets = int(parts[1])
    cleanliness = int(parts[2])
    behavior = int(parts[3])
    extra = parts[4] if len(parts) == 5 else parts[4] + " " + parts[5]
    fields = extra.split("|")
    school = fields[0] if len(fields) > 0 else None
    district = fields[1] if len(fields) > 1 else None
    session = fields[2] if len(fields) > 2 else None
    rows = fields[3] if len(fields) > 3 else None
    info = fields[4] if len(fields) > 4 else None

    payload = {
        "phone": phone,
        "tickets_count": tickets,
        "cleanliness_rating": cleanliness,
        "behavior_rating": behavior,
        "school": school,
        "district": district,
        "session_info": session,
        "seats_rows": rows,
        "extra_info": info,
        "created_at": now_iso(),
        "photo_path": None,
    }
    _PENDING[message.from_user.id] = payload
    await message.answer("Запись подготовлена. Отправьте фото с подписью class_photo или /class_save без фото")


@router.message(F.text == "/class_save")
async def class_save(message: Message) -> None:
    payload = _PENDING.pop(message.from_user.id, None)
    if not payload:
        await message.answer("Нет подготовленной записи")
        return
    await classes.add_visit(payload)
    await message.answer("Запись класса сохранена")


@router.message(F.photo)
async def class_photo(message: Message) -> None:
    if not message.caption or "class_photo" not in message.caption:
        return
    payload = _PENDING.get(message.from_user.id)
    if not payload:
        await message.answer("Сначала /class_add ...")
        return

    target = build_media_path("classes", payload["phone"])
    await message.bot.download(message.photo[-1], destination=target)
    payload["photo_path"] = str(target)
    await classes.add_visit(payload)
    _PENDING.pop(message.from_user.id, None)
    await message.answer("Запись класса с фото сохранена")


@router.message(F.text.startswith("/class_find "))
async def class_find(message: Message) -> None:
    phone_part = message.text.removeprefix("/class_find ").strip()
    rows = await classes.find_by_phone(phone_part)
    if not rows:
        await message.answer("Ничего не найдено")
        return
    lines = [f"{r['phone']} | билеты={r['tickets_count']} | чистота={r['cleanliness_rating']} | порядок={r['behavior_rating']} | {r.get('school') or '-'}" for r in rows]
    await message.answer("\n".join(lines))
