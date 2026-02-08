import asyncio
import logging
from datetime import datetime

from aiogram import Bot

from app.config import AppContext
from app.db import checklists, popcorn


async def run_background_jobs(bot: Bot, ctx: AppContext) -> None:
    while True:
        try:
            deleted = await popcorn.cleanup(ctx.settings.cleanup_days)
            if deleted:
                logging.info("Cleanup deleted popcorn rows: %s", deleted)

            reminders = await checklists.active_reminders()
            now = datetime.now()
            today = now.date().isoformat()
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

        await asyncio.sleep(3600)
