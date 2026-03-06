from typing import Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.config import AppContext
from app.db import faq
from app.services.auth import ensure_min_role
from app.ui.labels import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_FAQ,
    FAQ_ADD_ARTICLE,
    FAQ_ADD_STEP,
    FAQ_VIEW,
)
from app.utils.common import build_media_path, now_iso

router = Router()

FAQ_NEXT = "▶ Следующая"
FAQ_PREV = "◀ Предыдущая"
FAQ_PAGE_SIZE = 10

class FaqCreateStates(StatesGroup):
    title = State()


class FaqAddStepStates(StatesGroup):
    article_id = State()
    step_text = State()
    step_photo = State()


class FaqViewStates(StatesGroup):
    article_id = State()


def _faq_menu_kb(is_admin: bool) -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=FAQ_VIEW)
    if is_admin:
        kb.button(text=FAQ_ADD_ARTICLE)
        kb.button(text=FAQ_ADD_STEP)
    kb.button(text=BTN_BACK)
    kb.button(text=BTN_CANCEL)
    kb.adjust(2, 2, 1)
    return kb


def _articles_kb(rows: list[dict], page: int) -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    start = page * FAQ_PAGE_SIZE
    end = start + FAQ_PAGE_SIZE
    for row in rows[start:end]:
        kb.button(text=f"{row['id']}: {row['title']}")
    if page > 0:
        kb.button(text=FAQ_PREV)
    if end < len(rows):
        kb.button(text=FAQ_NEXT)
    kb.button(text=BTN_CANCEL)
    kb.button(text=BTN_BACK)
    kb.adjust(2, 2, 2, 1)
    return kb


def _parse_article_id(text: str) -> Optional[int]:
    text = text.strip()
    if ":" in text:
        text = text.split(":", maxsplit=1)[0]
    try:
        return int(text)
    except ValueError:
        return None


def _cancel_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_CANCEL)
    kb.button(text=BTN_BACK)
    kb.adjust(2)
    return kb


def _photo_skip_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text="Без фото")
    kb.button(text=BTN_CANCEL)
    kb.button(text=BTN_BACK)
    kb.adjust(2, 1)
    return kb


@router.message(F.text == BTN_FAQ)
async def faq_menu(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    is_admin = await ensure_min_role(message.from_user.id, "admin", ctx)
    await message.answer(
        "FAQ — выберите действие:",
        reply_markup=_faq_menu_kb(is_admin).as_markup(resize_keyboard=True),
    )


@router.message(F.text == FAQ_VIEW)
async def faq_view_start(message: Message, state: FSMContext) -> None:
    rows = await faq.list_articles()
    if not rows:
        await message.answer("Пока нет статей.")
        await faq_menu(message)
        return
    await state.update_data(faq_page=0)
    await state.set_state(FaqViewStates.article_id)
    await message.answer(
        "Выберите статью (страница 1):",
        reply_markup=_articles_kb(rows, 0).as_markup(resize_keyboard=True),
    )


@router.message(FaqViewStates.article_id)
async def faq_view_show(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await faq_menu(message)
        return
    if message.text in {FAQ_NEXT, FAQ_PREV}:
        data = await state.get_data()
        page = int(data.get("faq_page", 0))
        rows = await faq.list_articles()
        max_page = max(0, (len(rows) - 1) // FAQ_PAGE_SIZE)
        if message.text == FAQ_NEXT:
            page = min(page + 1, max_page)
        else:
            page = max(page - 1, 0)
        await state.update_data(faq_page=page)
        await message.answer(
            f"Выберите статью (страница {page + 1}):",
            reply_markup=_articles_kb(rows, page).as_markup(resize_keyboard=True),
        )
        return
    article_id = _parse_article_id(message.text)
    if article_id is None:
        await message.answer("Выберите статью из списка.")
        return
    article = await faq.get_article(article_id)
    if not article:
        await message.answer("Статья не найдена.")
        return
    steps = await faq.get_steps(article_id)
    await state.clear()
    await message.answer(f"Статья: {article['title']}")
    if not steps:
        await message.answer("Шагов пока нет.")
        await faq_menu(message)
        return
    for step in steps:
        caption = f"Шаг {step['step_index']}: {step['text']}"
        if step.get("photo_path"):
            try:
                await message.answer_photo(photo=FSInputFile(step["photo_path"]), caption=caption)
            except FileNotFoundError:
                await message.answer(caption + "\n(фото не найдено)")
        else:
            await message.answer(caption)
    await faq_menu(message)


@router.message(F.text == FAQ_ADD_ARTICLE)
async def faq_add_article_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(FaqCreateStates.title)
    await message.answer("Введите название статьи:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(FaqCreateStates.title)
async def faq_add_article_title(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await faq_menu(message)
        return
    title = message.text.strip()
    if not title:
        await message.answer("Название не может быть пустым.")
        return
    article_id = await faq.create_article(title, message.from_user.id, now_iso())
    await state.update_data(article_id=article_id)
    await state.set_state(FaqAddStepStates.step_text)
    await message.answer(
        f"Статья создана (ID {article_id}). Отправьте текст шага 1:",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


@router.message(F.text == FAQ_ADD_STEP)
async def faq_add_step_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    rows = await faq.list_articles()
    if not rows:
        await message.answer("Пока нет статей.")
        await faq_menu(message)
        return
    await state.update_data(faq_page=0)
    await state.set_state(FaqAddStepStates.article_id)
    await message.answer(
        "Выберите статью (страница 1):",
        reply_markup=_articles_kb(rows, 0).as_markup(resize_keyboard=True),
    )


@router.message(FaqAddStepStates.article_id)
async def faq_add_step_article(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await faq_menu(message)
        return
    if message.text in {FAQ_NEXT, FAQ_PREV}:
        data = await state.get_data()
        page = int(data.get("faq_page", 0))
        rows = await faq.list_articles()
        max_page = max(0, (len(rows) - 1) // FAQ_PAGE_SIZE)
        if message.text == FAQ_NEXT:
            page = min(page + 1, max_page)
        else:
            page = max(page - 1, 0)
        await state.update_data(faq_page=page)
        await message.answer(
            f"Выберите статью (страница {page + 1}):",
            reply_markup=_articles_kb(rows, page).as_markup(resize_keyboard=True),
        )
        return
    article_id = _parse_article_id(message.text)
    if article_id is None:
        await message.answer("Выберите статью из списка.")
        return
    article = await faq.get_article(article_id)
    if not article:
        await message.answer("Статья не найдена.")
        return
    await state.update_data(article_id=article_id)
    await state.set_state(FaqAddStepStates.step_text)
    await message.answer("Введите текст шага:", reply_markup=_cancel_kb().as_markup(resize_keyboard=True))


@router.message(FaqAddStepStates.step_text)
async def faq_add_step_text(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await faq_menu(message)
        return
    text = message.text.strip()
    if not text:
        await message.answer("Текст шага не может быть пустым.")
        return
    await state.update_data(step_text=text)
    await state.set_state(FaqAddStepStates.step_photo)
    await message.answer(
        "Отправьте фото шага или нажмите 'Без фото':",
        reply_markup=_photo_skip_kb().as_markup(resize_keyboard=True),
    )


@router.message(FaqAddStepStates.step_photo, F.photo)
async def faq_add_step_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    article_id = data["article_id"]
    text = data["step_text"]
    step_index = await faq.get_next_step_index(article_id)
    target = build_media_path("faq", f"{article_id}_{step_index}")
    await message.bot.download(message.photo[-1], destination=target)
    await faq.add_step(article_id, step_index, text, str(target), now_iso())
    await state.set_state(FaqAddStepStates.step_text)
    await message.answer(
        f"Шаг {step_index} добавлен. Отправьте следующий шаг или нажмите Назад.",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


@router.message(FaqAddStepStates.step_photo)
async def faq_add_step_no_photo(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await faq_menu(message)
        return
    if message.text != "Без фото":
        await message.answer("Отправьте фото или нажмите 'Без фото'.")
        return
    data = await state.get_data()
    article_id = data["article_id"]
    text = data["step_text"]
    step_index = await faq.get_next_step_index(article_id)
    await faq.add_step(article_id, step_index, text, None, now_iso())
    await state.set_state(FaqAddStepStates.step_text)
    await message.answer(
        f"Шаг {step_index} добавлен. Отправьте следующий шаг или нажмите Назад.",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )
