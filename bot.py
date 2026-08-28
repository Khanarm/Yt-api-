import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database import connect_to_mongo, close_mongo_connection
from utils.logger import logger
from handlers import start, plans, api_key, subscription, admin

async def main():
    logger.info("Connecting to MongoDB for Telegram Bot...")
    await connect_to_mongo()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Register routers
    dp.include_router(start.router)
    dp.include_router(plans.router)
    dp.include_router(api_key.router)
    dp.include_router(subscription.router)
    dp.include_router(admin.router)

    logger.info("Starting Telegram Bot Polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await close_mongo_connection()
        await bot.session.close()
        logger.info("Telegram Bot stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
