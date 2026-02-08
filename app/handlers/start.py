from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.config import AppContext
from app.db import users
from app.services.auth import ensure_min_role, get_role
from app.utils.common import now_iso

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🎟 Сертификаты")
    kb.button(text="🍿 Расход попкорна")
    kb.button(text="🏫 Рейтинг классов")
    kb.button(text="✅ Чек-листы")
    kb.button(text="📅 График")
    kb.adjust(2, 2, 1)

    ctx: AppContext = message.bot["ctx"]
    role = await get_role(message.from_user.id, ctx)

    await message.answer(
        f"Роль: {role}. Выберите раздел.",
        reply_markup=kb.as_markup(resize_keyboard=True),
    )


@router.message(F.text.startswith("/add_admin "))
async def add_admin(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "system_admin", ctx):
        await message.answer("Только системный администратор")
        return
    user_id = int(message.text.removeprefix("/add_admin ").strip())
    await users.set_role(user_id, "admin", now_iso())
    await message.answer(f"Пользователь {user_id} назначен администратором")


@router.message(F.text.startswith("/set_role "))
async def set_role(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3:
        await message.answer("Формат: /set_role USER_ID worker|admin")
        return
    role = parts[2].strip()
    if role not in {"worker", "admin"}:
        await message.answer("Разрешены только worker/admin")
        return
    await users.set_role(int(parts[1]), role, now_iso())
    await message.answer("Роль обновлена")
