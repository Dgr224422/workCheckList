from aiogram import F, Router
from aiogram.types import Message

from app.config import AppContext
from app.db import schedule
from app.services.auth import ensure_min_role
from app.utils.common import now_iso

router = Router()


@router.message(F.text == "📅 График")
async def schedule_menu(message: Message) -> None:
    await message.answer(
        "График:\n"
        "• /shift_add YYYY-MM-DD WORKER_NAME SHIFT_TIME [NOTES] (admin)\n"
        "• /shift_month YYYY-MM"
    )


@router.message(F.text.startswith("/shift_add "))
async def shift_add(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав")
        return

    parts = message.text.split(maxsplit=4)
    if len(parts) < 4:
        await message.answer("Формат: /shift_add YYYY-MM-DD WORKER_NAME SHIFT_TIME [NOTES]")
        return

    payload = {
        "work_date": parts[1],
        "worker_name": parts[2],
        "shift_time": parts[3],
        "notes": parts[4] if len(parts) > 4 else None,
        "created_by": message.from_user.id,
        "created_at": now_iso(),
    }
    await schedule.add_shift(payload)
    await message.answer("Смена добавлена")


@router.message(F.text.startswith("/shift_month "))
async def shift_month(message: Message) -> None:
    year_month = message.text.removeprefix("/shift_month ").strip()
    rows = await schedule.month_schedule(year_month)
    if not rows:
        await message.answer("Смен нет")
        return
    lines = [f"{r['work_date']} | {r['worker_name']} | {r['shift_time']} | {r.get('notes') or ''}" for r in rows]
    await message.answer("\n".join(lines[:100]))
