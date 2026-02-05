from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards import admin_keyboard, worker_keyboard


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    db = message.bot["db"]
    admin_ids = message.bot["admin_ids"]

    is_admin = message.from_user.id in admin_ids
    await db.register_user(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        is_admin=is_admin,
    )

    keyboard = admin_keyboard if is_admin else worker_keyboard
    role = "администратор" if is_admin else "сотрудник"
    await message.answer(
        f"Привет, {message.from_user.full_name}!\n"
        f"Ваша роль: {role}.\n"
        "Используйте кнопки меню для работы с чек-листами.",
        reply_markup=keyboard,
    )


@router.message(F.text == "⬅️ Назад")
async def back(message: Message) -> None:
    is_admin = message.from_user.id in message.bot["admin_ids"]
    await message.answer("Главное меню", reply_markup=admin_keyboard if is_admin else worker_keyboard)
