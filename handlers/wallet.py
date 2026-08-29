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
# CONSTANTS
# ==========================================================

# 100 half-star units = 50 Stars
MIN_WITHDRAW_HALF_STARS = int(
    getattr(
        settings,
        "WITHDRAW_MIN_HALF_STARS",
        100
    )
)


# ==========================================================
# HELPERS
# ==========================================================

def stars_from_half_units(value: int) -> float:
    return value / 2


def format_stars(value: int) -> str:
    stars = stars_from_half_units(value)

    if stars.is_integer():
        return f"{int(stars)}"

    return f"{stars:.1f}"


async def get_wallet(user_id: int) -> int:

    user = await db.db.users.find_one(
        {"user_id": user_id},
        {
            "wallet_half_stars": 1
        }
    )

    if not user:
        return 0

    return int(
        user.get(
            "wallet_half_stars",
            0
        )
    )


# ==========================================================
# WALLET KEYBOARD
# ==========================================================

def wallet_keyboard() -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Refer & Earn",
                    callback_data="wallet_referral"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💸 Withdraw Stars",
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


# ==========================================================
# WALLET SCREEN
# ==========================================================

async def show_wallet(
    message: Message,
    user_id: int,
    edit: bool = False
):

    try:

        user = await db.db.users.find_one({
            "user_id": user_id
        })

        if not user:

            text = (
                "❌ <b>User account not found.</b>\n\n"
                "Please send /start first."
            )

            if edit:
                await message.edit_text(
                    text,
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    text,
                    parse_mode="HTML"
                )

            return

        balance_half = int(
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

        balance = format_stars(
            balance_half
        )

        minimum = format_stars(
            MIN_WITHDRAW_HALF_STARS
        )

        remaining_half = max(
            0,
            MIN_WITHDRAW_HALF_STARS - balance_half
        )

        remaining = format_stars(
            remaining_half
        )

        if balance_half >= MIN_WITHDRAW_HALF_STARS:

            withdraw_status = (
                "✅ <b>Withdrawal available</b>"
            )

        else:

            withdraw_status = (
                f"🔒 Withdrawal unlocks at "
                f"<b>{minimum} ⭐</b>\n"
                f"Need <b>{remaining} ⭐</b> more"
            )

        text = (
            "💰 <b>Your Stars Wallet</b>\n\n"

            f"⭐ Balance: <b>{balance} Stars</b>\n"
            f"👥 Valid Referrals: "
            f"<b>{referral_count}</b>\n\n"

            f"🎁 Reward: <b>0.5 ⭐</b> per referral\n"
            f"💸 Minimum withdrawal: "
            f"<b>{minimum} ⭐</b>\n\n"

            f"{withdraw_status}\n\n"

            "You can also use your wallet balance "
            "to purchase API plans."
        )

        if edit:

            await message.edit_text(
                text,
                reply_markup=wallet_keyboard(),
                parse_mode="HTML"
            )

        else:

            await message.answer(
                text,
                reply_markup=wallet_keyboard(),
                parse_mode="HTML"
            )

    except Exception as e:

        logger.error(
            "Wallet screen error user=%s: %s",
            user_id,
            e,
            exc_info=True
        )

        await message.answer(
            "❌ Unable to load wallet. Please try again.",
            parse_mode="HTML"
        )


# ==========================================================
# /WALLET
# ==========================================================

@router.message(Command("wallet"))
async def cmd_wallet(
    message: Message
):

    await show_wallet(
        message=message,
        user_id=message.from_user.id
    )


# ==========================================================
# WALLET MENU
# ==========================================================

@router.callback_query(
    F.data == "menu_wallet"
)
async def callback_wallet(
    callback: CallbackQuery
):

    await show_wallet(
        message=callback.message,
        user_id=callback.from_user.id,
        edit=True
    )

    await callback.answer()


# ==========================================================
# REFERRAL LINK
# ==========================================================

async def get_referral_link(
    bot,
    user_id: int
) -> str:

    me = await bot.get_me()

    return (
        f"https://t.me/{me.username}"
        f"?start={user_id}"
    )


# ==========================================================
# REFERRAL SCREEN
# ==========================================================

async def show_referral(
    message: Message,
    user_id: int,
    bot,
    edit: bool = False
):

    user = await db.db.users.find_one({
        "user_id": user_id
    })

    if not user:

        text = (
            "❌ User not found.\n\n"
            "Please send /start first."
        )

        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)

        return

    referral_count = int(
        user.get(
            "referral_count",
            0
        )
    )

    balance_half = int(
        user.get(
            "wallet_half_stars",
            0
        )
    )

    balance = format_stars(
        balance_half
    )

    referral_link = await get_referral_link(
        bot,
        user_id
    )

    text = (
        "👥 <b>Refer & Earn</b>\n\n"

        "🎁 <b>Reward:</b> 0.5 ⭐ per valid referral\n\n"

        f"👥 Your referrals: "
        f"<b>{referral_count}</b>\n"

        f"💰 Wallet balance: "
        f"<b>{balance} ⭐</b>\n\n"

        "🔗 <b>Your referral link:</b>\n"
        f"<code>{referral_link}</code>\n\n"

        "Share this link with your friends.\n"
        "When a new valid user joins through your link, "
        "you receive <b>0.5 ⭐</b>."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 Share Referral Link",
                    url=(
                        "https://t.me/share/url"
                        f"?url={referral_link}"
                    )
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
                    text="🔙 Main Menu",
                    callback_data="menu_home"
                )
            ]
        ]
    )

    if edit:

        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    else:

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# ==========================================================
# /REFER
# ==========================================================

@router.message(Command("refer"))
async def cmd_refer(
    message: Message
):

    await show_referral(
        message=message,
        user_id=message.from_user.id,
        bot=message.bot
    )


# ==========================================================
# REFERRAL CALLBACK
# ==========================================================

@router.callback_query(
    F.data == "wallet_referral"
)
async def callback_referral(
    callback: CallbackQuery
):

    await show_referral(
        message=callback.message,
        user_id=callback.from_user.id,
        bot=callback.bot,
        edit=True
    )

    await callback.answer()


# ==========================================================
# WITHDRAW SCREEN
# ==========================================================

@router.callback_query(
    F.data == "wallet_withdraw"
)
async def callback_withdraw(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    balance_half = await get_wallet(
        user_id
    )

    balance = format_stars(
        balance_half
    )

    minimum = format_stars(
        MIN_WITHDRAW_HALF_STARS
    )

    if balance_half < MIN_WITHDRAW_HALF_STARS:

        remaining = format_stars(
            MIN_WITHDRAW_HALF_STARS -
            balance_half
        )

        await callback.answer(
            (
                f"❌ You need {remaining} more Stars.\n"
                f"Minimum withdrawal is {minimum} ⭐."
            ),
            show_alert=True
        )

        return

    await callback.message.edit_text(
        "💸 <b>Withdraw Stars</b>\n\n"

        f"⭐ Available: <b>{balance} Stars</b>\n"
        f"🎯 Minimum: <b>{minimum} Stars</b>\n\n"

        "Send the amount you want to withdraw.\n\n"

        "Example:\n"
        "<code>/withdraw 50</code>\n\n"

        "⚠️ Only whole Stars can be withdrawn.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Cancel",
                        callback_data="menu_wallet"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# WITHDRAW COMMAND
# ==========================================================

@router.message(Command("withdraw"))
async def cmd_withdraw(
    message: Message
):

    user_id = message.from_user.id

    parts = (
        message.text or ""
    ).split()

    if len(parts) < 2:

        minimum = format_stars(
            MIN_WITHDRAW_HALF_STARS
        )

        await message.answer(
            "💸 <b>Withdraw Stars</b>\n\n"
            f"Minimum withdrawal: "
            f"<b>{minimum} ⭐</b>\n\n"
            "Example:\n"
            "<code>/withdraw 50</code>",
            parse_mode="HTML"
        )

        return

    try:

        amount = float(parts[1])

    except ValueError:

        await message.answer(
            "❌ Invalid amount.\n\n"
            "Example: <code>/withdraw 50</code>",
            parse_mode="HTML"
        )

        return

    # Only whole Stars
    if not amount.is_integer():

        await message.answer(
            "❌ Withdrawal amount must be a whole number of Stars.",
            parse_mode="HTML"
        )

        return

    amount = int(amount)

    amount_half = amount * 2

    if amount_half < MIN_WITHDRAW_HALF_STARS:

        minimum = format_stars(
            MIN_WITHDRAW_HALF_STARS
        )

        await message.answer(
            f"❌ Minimum withdrawal is <b>{minimum} ⭐</b>.",
            parse_mode="HTML"
        )

        return

    # ======================================================
    # ATOMIC BALANCE LOCK
    # ======================================================

    now = datetime.now(timezone.utc)

    withdrawal_id = (
        f"WD_{user_id}_{int(now.timestamp())}"
    )

    result = await db.db.users.update_one(
        {
            "user_id": user_id,

            "wallet_half_stars": {
                "$gte": amount_half
            }
        },
        {
            "$inc": {
                "wallet_half_stars":
                    -amount_half
            }
        }
    )

    if result.modified_count != 1:

        current = await get_wallet(
            user_id
        )

        await message.answer(
            "❌ <b>Insufficient wallet balance.</b>\n\n"
            f"Your balance: "
            f"<b>{format_stars(current)} ⭐</b>",
            parse_mode="HTML"
        )

        return

    # ======================================================
    # CREATE WITHDRAWAL
    # ======================================================

    try:

        await db.db.withdrawals.insert_one({
            "withdrawal_id": withdrawal_id,

            "user_id": user_id,

            "amount_half_stars":
                amount_half,

            "amount_stars":
                amount,

            "status": "pending",

            "created_at": now,

            "processed_at": None,

            "processed_by": None,

            "note": None
        })

        # Ledger entry
        await db.db.wallet_transactions.insert_one({
            "transaction_id": withdrawal_id,

            "user_id": user_id,

            "type": "withdrawal",

            "amount_half_stars":
                -amount_half,

            "status": "pending",

            "created_at": now
        })

    except Exception as e:

        # ==================================================
        # REFUND IF WITHDRAWAL CREATION FAILS
        # ==================================================

        await db.db.users.update_one(
            {
                "user_id": user_id
            },
            {
                "$inc": {
                    "wallet_half_stars":
                        amount_half
                }
            }
        )

        logger.error(
            "Withdrawal creation failed: %s",
            e,
            exc_info=True
        )

        await message.answer(
            "❌ Withdrawal request failed.\n\n"
            "Your wallet balance has been restored.",
            parse_mode="HTML"
        )

        return

    await message.answer(
        "✅ <b>Withdrawal Request Created</b>\n\n"

        f"🆔 ID: <code>{withdrawal_id}</code>\n"
        f"⭐ Amount: <b>{amount} Stars</b>\n"
        "📌 Status: <b>Pending</b>\n\n"

        "Your request has been submitted for processing.",
        parse_mode="HTML"
    )


# ==========================================================
# TRANSACTION HISTORY
# ==========================================================

@router.callback_query(
    F.data == "wallet_transactions"
)
async def wallet_transactions(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    transactions = (
        await db.db.wallet_transactions
        .find({
            "user_id": user_id
        })
        .sort(
            "created_at",
            -1
        )
        .limit(15)
        .to_list(
            length=15
        )
    )

    if not transactions:

        text = (
            "📜 <b>Wallet Transactions</b>\n\n"
            "No transactions yet."
        )

    else:

        lines = [
            "📜 <b>Wallet Transactions</b>\n"
        ]

        for tx in transactions:

            amount_half = int(
                tx.get(
                    "amount_half_stars",
                    0
                )
            )

            amount = (
                stars_from_half_units(
                    abs(amount_half)
                )
            )

            tx_type = str(
                tx.get(
                    "type",
                    "transaction"
                )
            )

            status = str(
                tx.get(
                    "status",
                    "completed"
                )
            )

            if amount_half > 0:
                sign = "+"

            else:
                sign = "-"

            if amount.is_integer():
                amount_text = str(
                    int(amount)
                )
            else:
                amount_text = f"{amount:.1f}"

            lines.append(
                f"• {tx_type.replace('_', ' ').title()}\n"
                f"  {sign}{amount_text} ⭐ "
                f"({status})"
            )

        text = "\n".join(lines)

    await callback.message.edit_text(
        text,

        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💰 Wallet",
                        callback_data="menu_wallet"
                    )
                ]
            ]
        ),

        parse_mode="HTML"
    )

    await callback.answer()
