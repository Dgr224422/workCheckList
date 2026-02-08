import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.config import load_settings
from app.db import certificates, popcorn
from app.handlers.start import router as start_router
from app.logging_conf import setup_logging


async def on_startup() -> None:
    await certificates.init()
    await popcorn.init()


async def main() -> None:
    setup_logging()
    settings = load_settings()
    await on_startup()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(start_router)

    logging.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
