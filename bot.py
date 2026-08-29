import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from database import (
    connect_to_mongo,
    close_mongo_connection
)
from utils.logger import logger

# ==========================================================
# HANDLERS
# ==========================================================

from handlers import (
    start,
    plans,
    api_key,
    subscription,
    admin,
    wallet,
)

from handlers.admin_wallet import (
    router as admin_wallet_router
)


# ==========================================================
# MAIN
# ==========================================================

async def main():

    logger.info(
        "Connecting to MongoDB for Telegram Bot..."
    )

    await connect_to_mongo()

    bot = Bot(
        token=settings.BOT_TOKEN,

        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    # ======================================================
    # REGISTER ROUTERS
    # ======================================================

    dp.include_router(start.router)

    dp.include_router(plans.router)

    dp.include_router(api_key.router)

    dp.include_router(subscription.router)

    dp.include_router(admin.router)

    # Wallet:
    # /wallet
    # Referral
    # Withdraw
    # Transactions
    dp.include_router(wallet.router)

    # Admin withdrawal:
    # /withdrawals
    # Approve
    # Reject
    dp.include_router(admin_wallet_router)

    # ======================================================
    # START POLLING
    # ======================================================

    logger.info(
        "Starting Telegram Bot Polling..."
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        logger.info(
            "Stopping Telegram Bot..."
        )

        await close_mongo_connection()

        await bot.session.close()

        logger.info(
            "Telegram Bot stopped."
        )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except (
        KeyboardInterrupt,
        SystemExit
    ):

        logger.info(
            "Bot stopped by user."
        )
