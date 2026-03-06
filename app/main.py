import asyncio
import logging
from pathlib import Path
import sys

if __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import load_context
from app.db import certificates, popcorn, classes, checklists, schedule, users, faq, posters
from app.handlers.start import router as start_router
from app.handlers.certificates import router as cert_router
from app.handlers.popcorn import router as popcorn_router
from app.handlers.classes import router as classes_router
from app.handlers.checklists import router as checklists_router
from app.handlers.schedule import router as schedule_router
from app.handlers.faq import router as faq_router
from app.handlers.posters import router as posters_router
from app.logging_conf import setup_logging
from app.services.scheduler import run_background_jobs


async def on_startup() -> None:
    await users.init()
    await certificates.init()
    await popcorn.init()
    await classes.init()
    await checklists.init()
    await schedule.init()
    await faq.init()
    await posters.init()


async def main() -> None:
    setup_logging()
    ctx = load_context()
    await on_startup()

    bot = Bot(token=ctx.settings.bot_token)
    bot.ctx = ctx
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(start_router)
    dp.include_router(cert_router)
    dp.include_router(popcorn_router)
    dp.include_router(classes_router)
    dp.include_router(checklists_router)
    dp.include_router(schedule_router)
    dp.include_router(faq_router)
    dp.include_router(posters_router)

    asyncio.create_task(run_background_jobs(bot, ctx))

    logging.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
