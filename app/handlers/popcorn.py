from dataclasses import asdict

from aiogram import F, Router
from aiogram.types import Message

from app.config import AppContext
from app.db import popcorn
from app.services.auth import ensure_min_role
from app.services.popcorn import PopcornCalcInput, calculate
from app.utils.common import build_media_path, now_iso, today_date

router = Router()
_PENDING: dict[int, dict] = {}


@router.message(F.text == "🍿 Расход попкорна")
async def popcorn_menu(message: Message) -> None:
    await message.answer(
        "Попкорн:\n"
        "1) /popcorn SIZE WAREHOUSE_MORNING SLEEVES_TAKEN SOLD_CASHIER TZ_LEFT [YESTERDAY_END]\n"
        "2) Отправьте фото с подписью popcorn_photo"
    )


@router.message(F.text.startswith("/popcorn "))
async def popcorn_prepare(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "worker", ctx):
        await message.answer("Недостаточно прав.")
        return

    parts = message.text.split()
    if len(parts) not in (6, 7):
        await message.answer("Формат: /popcorn SIZE WAREHOUSE_MORNING SLEEVES_TAKEN SOLD_CASHIER TZ_LEFT [YESTERDAY_END]")
        return

    bucket_size = float(parts[1])
    warehouse_morning = int(parts[2])
    sleeves_taken = int(parts[3])
    sold_cashier = int(parts[4])
    tz_left = int(parts[5])
    yesterday_end = int(parts[6]) if len(parts) == 7 else await popcorn.get_last_end_of_day(bucket_size)
    if yesterday_end is None:
        await message.answer("Не найден вчерашний остаток. Передайте YESTERDAY_END вручную 7-м параметром.")
        return

    calc_input = PopcornCalcInput(
        bucket_size=bucket_size,
        yesterday_end=yesterday_end,
        warehouse_morning=warehouse_morning,
        sleeves_taken=sleeves_taken,
        sold_cashier=sold_cashier,
        tz_left=tz_left,
    )
    result = calculate(calc_input)
    _PENDING[message.from_user.id] = {
        "input": asdict(calc_input),
        "result": asdict(result),
    }

    await message.answer(
        "Данные для расчёта:\n"
        f"• Объём: {bucket_size}л\n"
        f"• Вчера конец дня: {yesterday_end}\n"
        f"• Склад утром: {warehouse_morning}\n"
        f"• Рукавов взяли: {sleeves_taken}\n"
        f"• Продано по кассе: {sold_cashier}\n"
        f"• Остаток ТЗ: {tz_left}\n\n"
        "Теперь отправьте фото отчёта с подписью popcorn_photo"
    )


@router.message(F.photo)
async def popcorn_photo(message: Message) -> None:
    if not message.caption or "popcorn_photo" not in message.caption:
        return
    pending = _PENDING.get(message.from_user.id)
    if not pending:
        await message.answer("Сначала выполните команду /popcorn ...")
        return

    photo = message.photo[-1]
    target = build_media_path("popcorn", f"{message.from_user.id}_{pending['input']['bucket_size']}")
    await message.bot.download(photo, destination=target)

    payload = {
        "report_date": today_date(),
        "bucket_size": pending["input"]["bucket_size"],
        "yesterday_end": pending["input"]["yesterday_end"],
        "warehouse_morning": pending["input"]["warehouse_morning"],
        "sleeves_taken": pending["input"]["sleeves_taken"],
        "sold_cashier": pending["input"]["sold_cashier"],
        "tz_left": pending["input"]["tz_left"],
        "warehouse_after_take": pending["result"]["warehouse_after_take"],
        "end_of_day": pending["result"]["end_of_day"],
        "cashier_expected": pending["result"]["cashier_expected"],
        "delta": pending["result"]["delta"],
        "photo_path": str(target),
        "created_at": now_iso(),
    }
    await popcorn.add_record(payload)
    _PENDING.pop(message.from_user.id, None)

    await message.answer(
        "Отчёт сохранён:\n"
        f"Остаток на складе: {payload['warehouse_after_take']}\n"
        f"Остаток конца дня: {payload['end_of_day']}\n"
        f"Ожидаемо по кассе: {payload['cashier_expected']}\n"
        f"Расхождение: {payload['delta']}"
    )


@router.message(F.text.startswith("/popcorn_report "))
async def popcorn_report(message: Message) -> None:
    days = int(message.text.removeprefix("/popcorn_report ").strip())
    rows = await popcorn.report(days)
    if not rows:
        await message.answer("Нет данных")
        return
    lines = [f"{r['report_date']} | {r['bucket_size']}л | касса={r['sold_cashier']} | ожидалось={r['cashier_expected']} | Δ={r['delta']}" for r in rows[:40]]
    await message.answer("\n".join(lines))
