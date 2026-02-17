from dataclasses import asdict
from typing import Any, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.config import AppContext
from app.db import popcorn
from app.services.auth import ensure_min_role
from app.services.popcorn import PopcornCalcInput, calculate
from app.ui.labels import (
    BTN_BACK,
    BTN_CANCEL,
    BTN_POPCORN,
    POPCORN_NEW,
    POPCORN_REPORT,
    POPCORN_PHOTOS,
    POPCORN_SUPPLY,
    POPCORN_STOCK,
)
from app.utils.common import build_media_path, now_iso, today_date

router = Router()


class PopcornStates(StatesGroup):
    warehouse_morning = State()
    sleeves_taken = State()
    sold_cashier = State()
    tz_left = State()
    yesterday_end = State()
    photo = State()
    report_days = State()
    supply_size = State()
    supply_quantity = State()


POPCORN_SIZES = [1.5, 3.0, 6.0]


def _size_label(size: float) -> str:
    return f"{size:.1f}"


async def _start_next_size(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    sizes = data.get("sizes", POPCORN_SIZES)
    index = data.get("size_index", 0)
    if index >= len(sizes):
        await state.clear()
        await message.answer("Отчёты сохранены.")
        await popcorn_menu(message)
        return

    size = sizes[index]
    await state.update_data(bucket_size=size)
    await state.set_state(PopcornStates.warehouse_morning)
    await message.answer(
        f"Отчёт для {_size_label(size)}л.\nСклад утром (целое число):",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


def _popcorn_menu_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=POPCORN_NEW)
    kb.button(text=POPCORN_REPORT)
    kb.button(text=POPCORN_PHOTOS)
    kb.button(text=POPCORN_SUPPLY)
    kb.button(text=POPCORN_STOCK)
    kb.button(text=BTN_BACK)
    kb.adjust(2, 2, 1)
    return kb


def _cancel_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BTN_CANCEL)
    kb.button(text=BTN_BACK)
    kb.adjust(2)
    return kb


def _sizes_kb() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    for size in POPCORN_SIZES:
        kb.button(text=_size_label(size))
    kb.button(text=BTN_CANCEL)
    kb.button(text=BTN_BACK)
    kb.adjust(3, 2)
    return kb


async def _calc_current_stock(size: float) -> tuple[int, Optional[dict[str, Any]]]:
    last_report = await popcorn.get_last_report(size)
    base_end = last_report["end_of_day"] if last_report else 0
    since_iso = last_report["created_at"] if last_report else None
    supply_total = await popcorn.supply_total_since(size, since_iso)
    current_warehouse = base_end + supply_total
    return current_warehouse, last_report


@router.message(F.text == BTN_POPCORN)
async def popcorn_menu(message: Message) -> None:
    await message.answer(
        "Попкорн — выберите действие:",
        reply_markup=_popcorn_menu_kb().as_markup(resize_keyboard=True),
    )


@router.message(F.text == POPCORN_NEW)
async def popcorn_new(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.update_data(sizes=POPCORN_SIZES, size_index=0)
    await _start_next_size(message, state)


@router.message(F.text == POPCORN_SUPPLY)
async def popcorn_supply_start(message: Message, state: FSMContext) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    await state.set_state(PopcornStates.supply_size)
    await message.answer(
        "Поставка ведер: выберите размер.",
        reply_markup=_sizes_kb().as_markup(resize_keyboard=True),
    )


@router.message(F.text == POPCORN_STOCK)
async def popcorn_stock_view(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return
    lines: list[str] = ["Остаток на складе:"]
    for size in POPCORN_SIZES:
        stock = await popcorn.get_stock(size)
        if stock is None:
            current_warehouse, _ = await _calc_current_stock(size)
            await popcorn.set_stock(size, current_warehouse, now_iso())
            stock = current_warehouse
        lines.append(f"{_size_label(size)}л: {stock}")
    await message.answer("\n".join(lines))


@router.message(PopcornStates.supply_size)
async def popcorn_supply_size(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    try:
        size = float(message.text.replace(",", ".").strip())
    except ValueError:
        await message.answer("Введите размер: 1.5, 3.0 или 6.0.")
        return
    if size not in POPCORN_SIZES:
        await message.answer("Введите размер: 1.5, 3.0 или 6.0.")
        return
    await state.update_data(bucket_size=size)
    await state.set_state(PopcornStates.supply_quantity)
    await message.answer(
        f"{_size_label(size)}л. Сколько ведер приехало (целое число):",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


@router.message(PopcornStates.supply_quantity)
async def popcorn_supply_quantity(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    try:
        quantity = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    if quantity <= 0:
        await message.answer("Количество должно быть больше нуля.")
        return
    data = await state.get_data()
    size = data["bucket_size"]
    ts = now_iso()
    await popcorn.add_supply(
        {
            "supply_date": today_date(),
            "bucket_size": size,
            "quantity": quantity,
            "created_at": ts,
        }
    )
    current_stock = await popcorn.get_stock(size)
    if current_stock is None:
        current_warehouse, last_report = await _calc_current_stock(size)
        await popcorn.set_stock(size, current_warehouse, ts)
    else:
        await popcorn.add_stock(size, quantity, ts)
        current_warehouse = current_stock + quantity
        last_report = await popcorn.get_last_report(size)
    note = ""
    if last_report is None:
        note = "\nВчерашний остаток не найден, считаю 0."
    await state.clear()
    await message.answer(
        f"Поставка принята: {_size_label(size)}л, {quantity} ведер.\n"
        f"Текущий склад: {current_warehouse}."
        f"{note}"
    )
    await popcorn_menu(message)


@router.message(PopcornStates.warehouse_morning)
async def popcorn_warehouse_morning(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    data = await state.get_data()
    size = data["bucket_size"]
    await state.update_data(warehouse_morning=value)
    await state.set_state(PopcornStates.sleeves_taken)
    await message.answer(
        f"{_size_label(size)}л. Сколько рукавов взяли:",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


@router.message(PopcornStates.sleeves_taken)
async def popcorn_sleeves_taken(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    data = await state.get_data()
    size = data["bucket_size"]
    await state.update_data(sleeves_taken=value)
    await state.set_state(PopcornStates.sold_cashier)
    await message.answer(
        f"{_size_label(size)}л. Продано по кассе:",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


@router.message(PopcornStates.sold_cashier)
async def popcorn_sold_cashier(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    data = await state.get_data()
    size = data["bucket_size"]
    await state.update_data(sold_cashier=value)
    await state.set_state(PopcornStates.tz_left)
    await message.answer(
        f"{_size_label(size)}л. Остаток ТЗ:",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


@router.message(PopcornStates.tz_left)
async def popcorn_tz_left(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    await state.update_data(tz_left=value)
    data = await state.get_data()
    size = data["bucket_size"]
    yesterday_end = await popcorn.get_last_end_of_day(size)
    if yesterday_end is None:
        await state.set_state(PopcornStates.yesterday_end)
        await message.answer(
            f"{_size_label(size)}л. Не найден вчерашний остаток. Введите вручную:",
            reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
        )
        return
    await _prepare_popcorn_result(message, state, yesterday_end)


@router.message(PopcornStates.yesterday_end)
async def popcorn_yesterday_end(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    await _prepare_popcorn_result(message, state, value)


async def _prepare_popcorn_result(message: Message, state: FSMContext, yesterday_end: int) -> None:
    data = await state.get_data()
    size = data["bucket_size"]
    calc_input = PopcornCalcInput(
        bucket_size=size,
        yesterday_end=yesterday_end,
        warehouse_morning=data["warehouse_morning"],
        sleeves_taken=data["sleeves_taken"],
        sold_cashier=data["sold_cashier"],
        tz_left=data["tz_left"],
    )
    result = calculate(calc_input)
    await state.update_data(
        yesterday_end=yesterday_end,
        result=asdict(result),
    )
    await state.set_state(PopcornStates.photo)
    await message.answer(
        f"Расчёт готов для {_size_label(size)}л:\n"
        f"• Остаток на складе: {result.warehouse_after_take}\n"
        f"• Остаток конца дня: {result.end_of_day}\n"
        f"• По факту: {result.cashier_expected}\n"
        f"• Расхождение: {result.delta:+d}\n\n"
        "Теперь отправьте фото отчёта.",
        reply_markup=_cancel_kb().as_markup(resize_keyboard=True),
    )


@router.message(PopcornStates.photo, F.photo)
async def popcorn_photo(message: Message, state: FSMContext) -> None:
    pending = await state.get_data()
    photo = message.photo[-1]
    target = build_media_path("popcorn", f"{message.from_user.id}_{pending['bucket_size']}")
    await message.bot.download(photo, destination=target)

    payload = {
        "report_date": today_date(),
        "bucket_size": pending["bucket_size"],
        "yesterday_end": pending["yesterday_end"],
        "warehouse_morning": pending["warehouse_morning"],
        "sleeves_taken": pending["sleeves_taken"],
        "sold_cashier": pending["sold_cashier"],
        "tz_left": pending["tz_left"],
        "warehouse_after_take": pending["result"]["warehouse_after_take"],
        "end_of_day": pending["result"]["end_of_day"],
        "cashier_expected": pending["result"]["cashier_expected"],
        "delta": pending["result"]["delta"],
        "photo_path": str(target),
        "created_at": now_iso(),
    }
    await popcorn.add_record(payload)
    await popcorn.set_stock(payload["bucket_size"], payload["end_of_day"], payload["created_at"])
    await message.answer(
        f"Отчёт {_size_label(payload['bucket_size'])}л сохранён:\n"
        f"Остаток на складе: {payload['warehouse_after_take']}\n"
        f"Остаток конца дня: {payload['end_of_day']}\n"
        f"По факту: {payload['cashier_expected']}\n"
        f"Расхождение: {payload['delta']:+d}"
    )

    sizes = pending.get("sizes")
    index = pending.get("size_index")
    if not sizes or index is None:
        await state.clear()
        await popcorn_menu(message)
        return
    await state.update_data(size_index=index + 1)
    await _start_next_size(message, state)


@router.message(PopcornStates.photo)
async def popcorn_photo_missing(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    await message.answer("Нужно отправить фото отчёта.")


@router.message(F.text == POPCORN_REPORT)
async def popcorn_report_start(message: Message, state: FSMContext) -> None:
    await state.set_state(PopcornStates.report_days)
    kb = ReplyKeyboardBuilder()
    kb.button(text="7")
    kb.button(text="14")
    kb.button(text="28")
    kb.button(text=BTN_CANCEL)
    kb.adjust(3, 1)
    await message.answer("За сколько дней показать отчёт:", reply_markup=kb.as_markup(resize_keyboard=True))


@router.message(PopcornStates.report_days)
async def popcorn_report_days(message: Message, state: FSMContext) -> None:
    if message.text in {BTN_CANCEL, BTN_BACK}:
        await state.clear()
        await popcorn_menu(message)
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("Введите 7, 14 или 28.")
        return
    if days not in {7, 14, 28}:
        await message.answer("Введите 7, 14 или 28.")
        return
    rows = await popcorn.report(days)
    await state.clear()
    if not rows:
        await message.answer("Нет данных.")
        await popcorn_menu(message)
        return
    lines: list[str] = []
    current_date = None
    total_cashier = 0
    total_expected = 0
    total_delta = 0
    for row in rows:
        if row["report_date"] != current_date:
            if current_date is not None:
                lines.append(
                    f"Итого: по кассе={total_cashier} | по факту={total_expected} | расхождение={total_delta:+d}"
                )
            current_date = row["report_date"]
            total_cashier = 0
            total_expected = 0
            total_delta = 0
            lines.append(current_date)
        total_cashier += row["sold_cashier"]
        total_expected += row["cashier_expected"]
        total_delta += row["delta"]
        lines.append(
            f"{_size_label(row['bucket_size'])}л | по кассе={row['sold_cashier']} | "
            f"по факту={row['cashier_expected']} | расхождение={row['delta']:+d}"
        )
    if current_date is not None:
        lines.append(
            f"Итого: по кассе={total_cashier} | по факту={total_expected} | расхождение={total_delta:+d}"
        )
    await message.answer("\n".join(lines[:80]))
    await popcorn_menu(message)


@router.message(F.text == POPCORN_PHOTOS)
async def popcorn_photos(message: Message) -> None:
    ctx: AppContext = message.bot.ctx
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав.")
        return
    rows = await popcorn.recent_photos(limit=10)
    if not rows:
        await message.answer("Фото не найдены.")
        return
    for row in rows:
        caption = f"{row['report_date']} | {row['bucket_size']}л | {row['created_at']}"
        try:
            await message.answer_photo(photo=FSInputFile(row["photo_path"]), caption=caption)
        except FileNotFoundError:
            await message.answer(f"Не найден файл: {row['photo_path']}")
