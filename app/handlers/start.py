from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

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

    await message.answer(
        "Выберите раздел. Для MVP реализованы базовые структуры и расчёт расхода попкорна.",
        reply_markup=kb.as_markup(resize_keyboard=True),
    )
