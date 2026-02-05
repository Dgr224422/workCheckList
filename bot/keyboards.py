from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


worker_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Выполнить чек-лист")],
        [KeyboardButton(text="📊 Мои отчеты")],
    ],
    resize_keyboard=True,
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Выполнить чек-лист")],
        [KeyboardButton(text="📊 Мои отчеты")],
        [KeyboardButton(text="⚙️ Админ-панель")],
    ],
    resize_keyboard=True,
)

admin_panel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Создать чек-лист")],
        [KeyboardButton(text="✏️ Добавить пункт")],
        [KeyboardButton(text="📋 Список чек-листов")],
        [KeyboardButton(text="📁 Отчеты сотрудников")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)
