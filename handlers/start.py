from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from datetime import datetime, timezone

from database import db
from config import settings
from utils.logger import logger


router = Router()


# ==========================================================
# MAIN MENU
# ==========================================================

def get_main_menu_keyboard() -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Plans",
                    callback_data="menu_plans"
                ),
                InlineKeyboardButton(
                    text="🔑 My API Key",
                    callback_data="menu_mykey"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 My Stats",
                    callback_data="menu_mystats"
                ),
                InlineKeyboardButton(
                    text="🔄 Renew",
                    callback_data="menu_renew"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Wallet",
                    callback_data="menu_wallet"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Refer & Earn",
                    callback_data="menu_referral"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📚 API Docs",
                    callback_data="menu_docs"
                ),
                InlineKeyboardButton(
                    text="🆘 Support",
                    callback_data="menu_support"
                )
            ]
        ]
    )


# ==========================================================
# REFERRAL REWARD
# ==========================================================

async def process_referral(
    new_user_id: int,
    referrer_id: int
):
    """
    Reward:
        1 valid referral = 0.5 Stars

    Internally:
        1 half-star unit = 0.5 Star

    Therefore:
        1 referral = 1 half-star unit
    """

    if not referrer_id:
        return

    # Self referral protection
    if referrer_id == new_user_id:
        return

    # Referrer must already exist
    referrer = await db.db.users.find_one({
        "user_id": referrer_id
    })

    if not referrer:
        return

    reward = int(
        getattr(
            settings,
            "REFERRAL_REWARD_HALF_STARS",
            1
        )
    )

    if reward <= 0:
        return

    transaction_id = f"REF_{new_user_id}"

    now = datetime.now(timezone.utc)

    try:

        # ------------------------------------------------------
        # Create referral transaction ONLY once
        # ------------------------------------------------------

        result = await db.db.referral_transactions.update_one(
            {
                "referral_user_id": new_user_id
            },
            {
                "$setOnInsert": {
                    "transaction_id": transaction_id,

                    "user_id": referrer_id,

                    "referral_user_id": new_user_id,

                    "amount_half_stars": reward,

                    "type": "referral_reward",

                    "status": "credited",

                    "created_at": now
                }
            },
            upsert=True
        )

        # ------------------------------------------------------
        # Only newly inserted referral gets reward
        # ------------------------------------------------------

        if result.upserted_id:

            wallet_result = await db.db.users.update_one(
                {
                    "user_id": referrer_id
                },
                {
                    "$inc": {
                        "wallet_half_stars": reward,
                        "referral_count": 1
                    }
                }
            )

            if wallet_result.modified_count:

                # Wallet ledger
                await db.db.wallet_transactions.insert_one({
                    "transaction_id": transaction_id,

                    "user_id": referrer_id,

                    "type": "referral_reward",

                    "amount_half_stars": reward,

                    "referral_user_id": new_user_id,

                    "created_at": now
                })

                logger.info(
                    "Referral reward credited | "
                    "referrer=%s referred=%s reward=%.1f Stars",
                    referrer_id,
                    new_user_id,
                    reward / 2
                )

    except Exception as e:

        logger.error(
            "Referral processing failed | "
            "new_user=%s referrer=%s error=%s",
            new_user_id,
            referrer_id,
            e,
            exc_info=True
        )


# ==========================================================
# /START
# ==========================================================

@router.message(Command("start"))
async def cmd_start(message: Message):

    user_id = message.from_user.id

    username = message.from_user.username

    first_name = (
        message.from_user.first_name
        or "User"
    )

    now = datetime.now(timezone.utc)

    # ======================================================
    # CHECK EXISTING USER
    # ======================================================

    existing = await db.db.users.find_one({
        "user_id": user_id
    })

    # ======================================================
    # NEW USER
    # ======================================================

    if not existing:

        referrer_id = None

        # Telegram deep-link:
        #
        # https://t.me/YOUR_BOT?start=123456789
        #
        # Aiogram gives:
        #
        # /start 123456789

        parts = (
            message.text or ""
        ).split(
            maxsplit=1
        )

        if len(parts) == 2:

            referral_code = (
                parts[1]
                .strip()
            )

            # Only numeric Telegram user IDs accepted
            if referral_code.isdigit():

                candidate = int(
                    referral_code
                )

                # Self referral protection
                if candidate != user_id:

                    referrer_exists = (
                        await db.db.users.find_one({
                            "user_id": candidate
                        })
                    )

                    if referrer_exists:

                        referrer_id = candidate

        # ==================================================
        # CREATE USER
        # ==================================================

        try:

            await db.db.users.insert_one({
                "user_id": user_id,

                "username": username,

                "created_at": now,

                "last_active": now,

                "referrer_id": referrer_id,

                # 1 unit = 0.5 Star
                "wallet_half_stars": 0,

                "referral_count": 0
            })

        except Exception as e:

            # Race condition:
            # If another request created the user
            # at the same time, continue normally.

            logger.warning(
                "User insert failed for %s: %s",
                user_id,
                e
            )

        # ==================================================
        # PROCESS REFERRAL
        # ==================================================

        if referrer_id:

            await process_referral(
                new_user_id=user_id,
                referrer_id=referrer_id
            )

    # ======================================================
    # EXISTING USER
    # ======================================================

    else:

        await db.db.users.update_one(
            {
                "user_id": user_id
            },
            {
                "$set": {
                    "username": username,

                    "last_active": now
                }
            }
        )

    # ======================================================
    # WELCOME
    # ======================================================

    welcome_text = (
        f"👋 Welcome, "
        f"<b>{first_name}</b>!\n\n"

        "🎵 <b>Music API Subscription Bot</b>\n\n"

        "💎 Buy an API plan\n"
        "🔑 Get your API key\n"
        "📊 Check your API usage\n"
        "👥 Refer users and earn Stars\n"
        "💰 Use your wallet to buy plans\n\n"

        "Select an option below:"
    )

    await message.answer(
        welcome_text,

        reply_markup=get_main_menu_keyboard(),

        parse_mode="HTML"
    )


# ==========================================================
# HOME BUTTON
# ==========================================================

@router.callback_query(
    F.data == "menu_home"
)
async def callback_home(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        "🏠 <b>Main Menu</b>\n\n"
        "Select an option below:",

        reply_markup=get_main_menu_keyboard(),

        parse_mode="HTML"
    )

    await callback.answer()
