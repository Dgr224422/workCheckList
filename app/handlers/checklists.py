from datetime import datetime

from aiogram import F, Router
from aiogram.types import Message

from app.config import AppContext
from app.db import checklists
from app.services.auth import ensure_min_role
from app.utils.common import build_media_path, now_iso, today_date

router = Router()


@router.message(F.text == "✅ Чек-листы")
async def checklists_menu(message: Message) -> None:
    await message.answer(
        "Чек-листы:\n"
        "• /check_template TITLE (admin)\n"
        "• /check_step TEMPLATE_ID TEXT (admin)\n"
        "• /check_list\n"
        "• /check_start TEMPLATE_ID\n"
        "• /check_view RUN_ID\n"
        "• /check_done RUN_STEP_ID\n"
        "• фото шага: подпись 'check_photo RUN_STEP_ID'\n"
        "• /reminder_add WORKER_ID TITLE|weekday:0-6 или date:YYYY-MM-DD"
    )


@router.message(F.text.startswith("/check_template "))
async def check_template(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав")
        return
    title = message.text.removeprefix("/check_template ").strip()
    template_id = await checklists.create_template(title, message.from_user.id, now_iso())
    await message.answer(f"Шаблон создан: {template_id}")


@router.message(F.text.startswith("/check_step "))
async def check_step(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав")
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /check_step TEMPLATE_ID TEXT")
        return
    template_id = int(parts[1])
    steps = await checklists.template_steps(template_id)
    await checklists.add_step(template_id, len(steps) + 1, parts[2])
    await message.answer("Шаг добавлен")


@router.message(F.text == "/check_list")
async def check_list(message: Message) -> None:
    templates = await checklists.list_templates()
    if not templates:
        await message.answer("Шаблоны не созданы")
        return
    await message.answer("\n".join([f"{t['id']}: {t['title']}" for t in templates]))


@router.message(F.text.startswith("/check_start "))
async def check_start(message: Message) -> None:
    template_id = int(message.text.removeprefix("/check_start ").strip())
    run_id = await checklists.create_run(template_id, message.from_user.id, today_date())
    await message.answer(f"Чек-лист запущен: RUN_ID={run_id}. Смотрите /check_view {run_id}")


@router.message(F.text.startswith("/check_view "))
async def check_view(message: Message) -> None:
    run_id = int(message.text.removeprefix("/check_view ").strip())
    steps = await checklists.run_steps(run_id)
    if not steps:
        await message.answer("Шаги не найдены")
        return
    lines = [f"{'✅' if s['is_done'] else '⬜️'} {s['run_step_id']}. {s['text']}" for s in steps]
    await message.answer("\n".join(lines))


@router.message(F.text.startswith("/check_done "))
async def check_done(message: Message) -> None:
    run_step_id = int(message.text.removeprefix("/check_done ").strip())
    await checklists.mark_run_step(run_step_id, None, now_iso())
    await message.answer("Шаг отмечен")


@router.message(F.photo)
async def check_photo(message: Message) -> None:
    if not message.caption or not message.caption.startswith("check_photo "):
        return
    run_step_id = int(message.caption.split(maxsplit=1)[1])
    target = build_media_path("checklists", str(run_step_id))
    await message.bot.download(message.photo[-1], destination=target)
    await checklists.mark_run_step(run_step_id, str(target), now_iso())
    await message.answer("Фото к шагу сохранено, шаг отмечен ✅")


@router.message(F.text.startswith("/reminder_add "))
async def reminder_add(message: Message) -> None:
    ctx: AppContext = message.bot["ctx"]
    if not await ensure_min_role(message.from_user.id, "admin", ctx):
        await message.answer("Недостаточно прав")
        return

    raw = message.text.removeprefix("/reminder_add ").strip()
    user_part, rest = raw.split(maxsplit=1)
    worker_id = int(user_part)
    title, schedule = rest.split("|", maxsplit=1)
    title = title.strip()
    schedule = schedule.strip()
    weekday = None
    exact_date = None
    if schedule.startswith("weekday:"):
        weekday = int(schedule.removeprefix("weekday:").strip())
    elif schedule.startswith("date:"):
        exact_date = schedule.removeprefix("date:").strip()
        datetime.strptime(exact_date, "%Y-%m-%d")
    else:
        await message.answer("Укажите weekday:0-6 или date:YYYY-MM-DD")
        return

    await checklists.add_reminder(worker_id, title, weekday, exact_date, now_iso())
    await message.answer("Напоминание добавлено")
