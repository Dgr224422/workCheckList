from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.config import AppContext
from app.db import users
from app.services.auth import ensure_min_role, get_role
from app.ui.labels import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_CERT,
    BTN_CHECKLISTS,
    BTN_CLASSES,
    BTN_FAQ,
    BTN_MAIN_MENU,
    BTN_POPCORN,
    BTN_SCHEDULE,
    ROLE_MENU,
)
from app.utils.common import now_iso

router = Router()


class RoleSetStates(StatesGroup):
    user_id = State()
    role = State()


def _main_menu_kb(is_admin: bool, is_system_admin: bool) -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_CERT)
    kb.button(text=BTN_POPCORN)
    kb.button(text=BTN_CLASSES)
    kb.button(text=BTN_CHECKLISTS)
    kb.button(text=BTN_SCHEDULE)
    kb.button(text=BTN_FAQ)
    if is_system_admin:
        kb.button(text=ROLE_MENU)
    kb.adjust(2, 2, 2, 1)
    return kb


async def _send_main_menu(message: Message, ctx: AppContext) -> None:
    role = await get_role(message.from_user.id, ctx)
    if role == "guest":
        return
    is_admin = await ensure_min_role(message.from_user.id, "admin", ctx)
    is_system_admin = role == "system_admin"
    await message.answer(
        f"Роль: {role}. Выберите раздел.",
        reply_markup=_main_menu_kb(is_admin, is_system_admin).as_markup(resize_keyboard=True),
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    ctx: AppContext = message.bot.ctx
    existing_role = await users.get_role(message.from_user.id)
    if existing_role is None and message.from_user.id != ctx.settings.system_admin_id and message.from_user.id not in ctx.admin_ids:
        await users.set_role(message.from_user.id, "guest", now_iso())
        await message.answer(
            "Добро пожаловать!\n"
            f"Ваш ID: {message.from_user.id}\n"
            "Передайте его системному администратору для выдачи роли.\n"
            "Доступ ограничен до назначения роли."
        )
        try:
            await message.bot.send_message(
                ctx.settings.system_admin_id,
                f"Новый пользователь: {message.from_user.id}. По умолчанию назначен guest.",
            )
        except Exception:
            pass
    await _send_main_menu(message, ctx)


@router.message(F.text.in_({BTN_MAIN_MENU, BTN_BACK}))
async def to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    ctx: AppContext = message.bot.ctx
    await _send_main_menu(message, ctx)


@router.message(F.text == ROLE_MENU)
async def role_menu(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "system_admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(RoleSetStates.user_id)
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_CANCEL)
    await message.answer("Введите ID пользователя:", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(RoleSetStates.user_id)
async def role_user_id(message: Message, state: FSMContext) -> None:
    if message.text == BTN_CANCEL:
        await state.clear()
        ctx: AppContext = message.bot.ctx
        await _send_main_menu(message, ctx)
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введите числовой ID пользователя.")
        return
    await state.update_data(user_id=user_id)
    await state.set_state(RoleSetStates.role)
    kb = ReplyKeyboardBuilder()
    kb.button(text="guest")
    kb.button(text="worker")
    kb.button(text="admin")
    kb.button(text=BTN_CANCEL)
    kb.adjust(2, 1)
    await message.answer("Выберите роль:", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(RoleSetStates.role)
async def role_set(message: Message, state: FSMContext) -> None:
    if message.text == BTN_CANCEL:
        await state.clear()
        ctx: AppContext = message.bot.ctx
        await _send_main_menu(message, ctx)
        return
    role = message.text.strip()
    if role not in {"guest", "worker", "admin"}:
        await message.answer("Разрешены только guest/worker/admin.")
        return
    data = await state.get_data()
    user_id = data["user_id"]
    await users.set_role(user_id, role, now_iso())
    await state.clear()
    await message.answer(f"Роль обновлена для {user_id}: {role}")
    ctx: AppContext = message.bot.ctx
    await _send_main_menu(message, ctx)
