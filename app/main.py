import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import load_context
from app.db import certificates, popcorn, classes, checklists, schedule, users
from app.handlers.start import router as start_router
from app.handlers.certificates import router as cert_router
from app.handlers.popcorn import router as popcorn_router
from app.handlers.classes import router as classes_router
from app.handlers.checklists import router as checklists_router
from app.handlers.schedule import router as schedule_router
from app.logging_conf import setup_logging
from app.services.scheduler import run_background_jobs


async def on_startup() -> None:
    await users.init()
    await certificates.init()
    await popcorn.init()
    await classes.init()
    await checklists.init()
    await schedule.init()
from app.config import load_settings
from app.db import certificates, popcorn
from app.handlers.start import router as start_router
from app.logging_conf import setup_logging


async def on_startup() -> None:
    await certificates.init()
    await popcorn.init()


async def main() -> None:
    setup_logging()
    ctx = load_context()
    await on_startup()

    bot = Bot(token=ctx.settings.bot_token)
    bot["ctx"] = ctx
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(cert_router)
    dp.include_router(popcorn_router)
    dp.include_router(classes_router)
    dp.include_router(checklists_router)
    dp.include_router(schedule_router)

    asyncio.create_task(run_background_jobs(bot, ctx))
    settings = load_settings()
    await on_startup()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(start_router)

    logging.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
