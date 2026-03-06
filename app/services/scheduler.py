import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot

from app.config import AppContext
from app.db import checklists, popcorn, posters, users
from app.utils.common import MOSCOW_TZ, now_iso_moscow, today_moscow


async def run_background_jobs(bot: Bot, ctx: AppContext) -> None:
    while True:
        try:
            deleted = await popcorn.cleanup(ctx.settings.cleanup_days)
            if deleted:
                logging.info("Cleanup deleted popcorn rows: %s", deleted)

            archived_deleted = await posters.cleanup_deleted(today_moscow().isoformat())
            if archived_deleted:
                logging.info("Cleanup deleted archived posters rows: %s", archived_deleted)

            await _run_poster_notifications(bot, ctx)

            reminders = await checklists.active_reminders()
            now = today_moscow()
            today = now.isoformat()
            weekday = now.weekday()
            for reminder in reminders:
                should_send = False
                if reminder["exact_date"] == today:
                    should_send = True
                if reminder["weekday"] is not None and int(reminder["weekday"]) == weekday:
                    should_send = True
                if should_send:
                    await bot.send_message(
                        reminder["worker_id"],
                        f"🔔 Напоминание: {reminder['title']}",
                    )
        except Exception:
            logging.exception("Background jobs failed")

        await asyncio.sleep(30)


async def _run_poster_notifications(bot: Bot, ctx: AppContext) -> None:
    now_msk = datetime.now(MOSCOW_TZ)
    if not (now_msk.hour == 14 and now_msk.minute == 0):
        return
    today = today_moscow()
    recipients = set(await users.list_non_guest_user_ids())
    recipients.update(ctx.admin_ids)
    recipients.discard(0)
    if not recipients:
        return

    for days_before in (4, 2):
        target_date = (today + timedelta(days=days_before)).isoformat()
        due = await posters.due_for_hang(target_date)
        if not due:
            continue

        lines = [f"{row['title']} — код {row['poster_code']}" for row in due]
        body = (
            f"Напоминание: до выхода фильмов {days_before} дня(ей).\\n"
            "Необходимо повесить постеры:\\n"
            + "\\n".join(lines)
            + "\\n\\nОткройте раздел «Постеры» → «Повесить постер»."
        )

        sent_date = today.isoformat()
        sent_at = now_iso_moscow()
        for user_id in recipients:
            should_send = False
            for row in due:
                is_new = await posters.log_notification_if_new(
                    poster_id=row["id"],
                    user_id=int(user_id),
                    days_before=days_before,
                    sent_date=sent_date,
                    sent_at=sent_at,
                )
                if is_new:
                    should_send = True
            if not should_send:
                continue
            try:
                await bot.send_message(int(user_id), body)
            except Exception:
                logging.exception("Failed to send poster reminder to %s", user_id)
