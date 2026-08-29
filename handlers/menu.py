from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database import db
from config import settings


router = Router()


# ==========================================================
# SETTINGS HELPERS
# ==========================================================

def get_setting(name: str, default: str = "") -> str:
    value = getattr(settings, name, default)

    if value is None:
        return default

    return str(value).strip()


# ==========================================================
# MAIN MENU
# ==========================================================

@router.callback_query(F.data == "menu_home")
async def menu_home(callback: CallbackQuery):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Wallet",
                    callback_data="menu_wallet"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 Buy API",
                    callback_data="menu_plans"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Referral",
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

    await callback.message.edit_text(
        "🏠 <b>Main Menu</b>\n\n"
        "Choose an option below:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# REFERRAL
# ==========================================================

@router.callback_query(F.data == "menu_referral")
async def menu_referral(callback: CallbackQuery):

    user_id = callback.from_user.id

    # Get bot username
    bot_info = await callback.bot.get_me()

    referral_link = (
        f"https://t.me/{bot_info.username}"
        f"?start={user_id}"
    )

    user = await db.db.users.find_one(
        {
            "user_id": user_id
        },
        {
            "referral_count": 1,
            "wallet_half_stars": 1
        }
    )

    referral_count = 0
    wallet_half_stars = 0

    if user:

        referral_count = int(
            user.get(
                "referral_count",
                0
            )
        )

        wallet_half_stars = int(
            user.get(
                "wallet_half_stars",
                0
            )
        )

    balance = wallet_half_stars / 2

    if balance.is_integer():
        balance_text = str(
            int(balance)
        )
    else:
        balance_text = f"{balance:.1f}"

    share_url = (
        "https://t.me/share/url"
        f"?url={referral_link}"
        "&text=Join%20this%20bot!"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Share Referral Link",
                    url=share_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 My Wallet",
                    callback_data="menu_wallet"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Main Menu",
                    callback_data="menu_home"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "👥 <b>Refer & Earn</b>\n\n"

        "🎁 <b>Reward:</b> 0.5 ⭐ per valid referral\n\n"

        f"👤 Your referrals: "
        f"<b>{referral_count}</b>\n"

        f"💰 Wallet balance: "
        f"<b>{balance_text} ⭐</b>\n\n"

        "🔗 <b>Your referral link:</b>\n"
        f"<code>{referral_link}</code>\n\n"

        "Share your link with friends and earn "
        "<b>0.5 ⭐</b> for every valid new referral.\n\n"

        "💸 Minimum withdrawal: <b>50 ⭐</b>",

        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# WALLET
# ==========================================================

@router.callback_query(F.data == "menu_wallet")
async def menu_wallet(callback: CallbackQuery):

    user_id = callback.from_user.id

    user = await db.db.users.find_one(
        {
            "user_id": user_id
        }
    )

    if not user:

        await callback.answer(
            "❌ Please send /start first.",
            show_alert=True
        )

        return

    wallet_half_stars = int(
        user.get(
            "wallet_half_stars",
            0
        )
    )

    referral_count = int(
        user.get(
            "referral_count",
            0
        )
    )

    balance = wallet_half_stars / 2

    if balance.is_integer():
        balance_text = str(
            int(balance)
        )
    else:
        balance_text = f"{balance:.1f}"

    if wallet_half_stars >= 100:
        withdrawal_text = (
            "✅ <b>Withdrawal available</b>"
        )
    else:
        remaining_half = (
            100 - wallet_half_stars
        )

        remaining = remaining_half / 2

        if remaining.is_integer():
            remaining_text = str(
                int(remaining)
            )
        else:
            remaining_text = f"{remaining:.1f}"

        withdrawal_text = (
            "🔒 Withdrawal requires "
            "<b>50 ⭐</b>\n"
            f"Need <b>{remaining_text} ⭐</b> more"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Refer & Earn",
                    callback_data="menu_referral"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💸 Withdraw",
                    callback_data="wallet_withdraw"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 Transactions",
                    callback_data="wallet_transactions"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 Buy API",
                    callback_data="menu_plans"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Refresh",
                    callback_data="menu_wallet"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Main Menu",
                    callback_data="menu_home"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "💰 <b>My Wallet</b>\n\n"

        f"⭐ Balance: <b>{balance_text} ⭐</b>\n"
        f"👥 Referrals: <b>{referral_count}</b>\n\n"

        "🎁 Referral reward: <b>0.5 ⭐</b>\n"
        "💸 Minimum withdrawal: <b>50 ⭐</b>\n\n"

        f"{withdrawal_text}\n\n"

        "💎 You can use your wallet balance "
        "to purchase API plans.",

        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# API DOCUMENTATION
# ==========================================================

@router.callback_query(F.data == "menu_docs")
async def menu_docs(callback: CallbackQuery):

    docs_url = get_setting(
        "API_DOCS_URL",
        ""
    )

    keyboard_buttons = []

    if docs_url:

        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text="📚 Open API Docs",
                    url=docs_url
                )
            ]
        )

    keyboard_buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Main Menu",
                callback_data="menu_home"
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=keyboard_buttons
    )

    if docs_url:

        text = (
            "📚 <b>API Documentation</b>\n\n"
            "API documentation open karne ke liye "
            "neeche button dabao.\n\n"
            "Yahan tum API endpoints, parameters "
            "aur usage examples dekh sakte ho."
        )

    else:

        text = (
            "📚 <b>API Documentation</b>\n\n"
            "API documentation abhi configure nahi hai.\n\n"
            "Admin ko <code>API_DOCS_URL</code> "
            "environment variable set karna hoga."
        )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# SUPPORT
# ==========================================================

@router.callback_query(F.data == "menu_support")
async def menu_support(callback: CallbackQuery):

    support_username = get_setting(
        "SUPPORT_USERNAME",
        ""
    )

    support_url = get_setting(
        "SUPPORT_URL",
        ""
    )

    if support_url:

        url = support_url

    elif support_username:

        username = support_username.lstrip("@")

        url = f"https://t.me/{username}"

    else:

        url = ""

    keyboard_buttons = []

    if url:

        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text="🆘 Contact Support",
                    url=url
                )
            ]
        )

    keyboard_buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Main Menu",
                callback_data="menu_home"
            )
        ]
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=keyboard_buttons
    )

    if url:

        text = (
            "🆘 <b>Support</b>\n\n"

            "Agar API, payment, wallet ya "
            "subscription me koi problem aa rahi hai "
            "to support se contact karo.\n\n"

            "👇 Neeche button se support team ko "
            "message karo."
        )

    else:

        text = (
            "🆘 <b>Support</b>\n\n"

            "Support contact abhi configure nahi hai.\n\n"

            "Admin ko <code>SUPPORT_USERNAME</code> "
            "ya <code>SUPPORT_URL</code> configure "
            "karna hoga."
        )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()
