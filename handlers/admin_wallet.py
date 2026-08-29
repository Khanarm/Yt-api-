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
# ADMIN CHECK
# ==========================================================

def is_admin(user_id: int) -> bool:
    admin_ids = getattr(
        settings,
        "ADMIN_IDS",
        []
    )

    if isinstance(admin_ids, int):
        admin_ids = [admin_ids]

    return user_id in admin_ids


# ==========================================================
# FORMAT
# ==========================================================

def format_stars(half_stars: int) -> str:

    stars = half_stars / 2

    if stars.is_integer():
        return str(int(stars))

    return f"{stars:.1f}"


# ==========================================================
# PENDING WITHDRAWALS
# ==========================================================

@router.message(Command("withdrawals"))
async def admin_withdrawals(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        await message.answer(
            "❌ You are not authorized."
        )

        return

    withdrawals = (
        await db.db.withdrawals
        .find({
            "status": "pending"
        })
        .sort(
            "created_at",
            1
        )
        .limit(20)
        .to_list(
            length=20
        )
    )

    if not withdrawals:

        await message.answer(
            "✅ <b>No pending withdrawals.</b>",
            parse_mode="HTML"
        )

        return

    for withdrawal in withdrawals:

        withdrawal_id = withdrawal[
            "withdrawal_id"
        ]

        user_id = withdrawal[
            "user_id"
        ]

        amount = int(
            withdrawal.get(
                "amount_stars",
                0
            )
        )

        created_at = withdrawal.get(
            "created_at"
        )

        if created_at:

            created_text = (
                created_at.strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
            )

        else:

            created_text = "Unknown"

        text = (
            "💸 <b>Pending Withdrawal</b>\n\n"

            f"🆔 ID:\n"
            f"<code>{withdrawal_id}</code>\n\n"

            f"👤 User ID:\n"
            f"<code>{user_id}</code>\n\n"

            f"⭐ Amount: "
            f"<b>{amount} Stars</b>\n"

            f"🕐 Created: "
            f"<code>{created_text}</code>\n"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Approve",
                        callback_data=(
                            f"wd_approve_{withdrawal_id}"
                        )
                    ),
                    InlineKeyboardButton(
                        text="❌ Reject",
                        callback_data=(
                            f"wd_reject_{withdrawal_id}"
                        )
                    )
                ]
            ]
        )

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# ==========================================================
# APPROVE WITHDRAWAL
# ==========================================================

@router.callback_query(
    F.data.startswith("wd_approve_")
)
async def approve_withdrawal(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "❌ Unauthorized.",
            show_alert=True
        )

        return

    withdrawal_id = callback.data.replace(
        "wd_approve_",
        "",
        1
    )

    withdrawal = await db.db.withdrawals.find_one({
        "withdrawal_id": withdrawal_id
    })

    if not withdrawal:

        await callback.answer(
            "❌ Withdrawal not found.",
            show_alert=True
        )

        return

    if withdrawal.get("status") != "pending":

        await callback.answer(
            "⚠️ This withdrawal is already processed.",
            show_alert=True
        )

        return

    user_id = int(
        withdrawal["user_id"]
    )

    amount = int(
        withdrawal.get(
            "amount_stars",
            0
        )
    )

    now = datetime.now(timezone.utc)

    # ======================================================
    # ATOMIC STATUS CHANGE
    # ======================================================

    result = await db.db.withdrawals.update_one(
        {
            "withdrawal_id": withdrawal_id,
            "status": "pending"
        },
        {
            "$set": {
                "status": "paid",

                "processed_at": now,

                "processed_by":
                    callback.from_user.id,

                "note":
                    "Withdrawal approved"
            }
        }
    )

    if result.modified_count != 1:

        await callback.answer(
            "⚠️ Already processed.",
            show_alert=True
        )

        return

    # ======================================================
    # UPDATE LEDGER
    # ======================================================

    await db.db.wallet_transactions.update_one(
        {
            "transaction_id":
                withdrawal_id
        },
        {
            "$set": {
                "status": "paid",

                "processed_at": now,

                "processed_by":
                    callback.from_user.id
            }
        }
    )

    # ======================================================
    # ADMIN MESSAGE
    # ======================================================

    await callback.message.edit_text(
        "✅ <b>Withdrawal Approved</b>\n\n"

        f"🆔 <code>{withdrawal_id}</code>\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"⭐ Amount: <b>{amount} Stars</b>\n\n"

        "Status: <b>PAID</b>",
        parse_mode="HTML"
    )

    await callback.answer(
        "Withdrawal approved."
    )

    # ======================================================
    # USER NOTIFICATION
    # ======================================================

    try:

        await callback.bot.send_message(
            user_id,

            "🎉 <b>Withdrawal Approved</b>\n\n"

            f"⭐ Amount: <b>{amount} Stars</b>\n"
            f"🆔 ID: <code>{withdrawal_id}</code>\n\n"

            "Your withdrawal has been approved.",
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            "Could not notify user %s: %s",
            user_id,
            e
        )


# ==========================================================
# REJECT WITHDRAWAL
# ==========================================================

@router.callback_query(
    F.data.startswith("wd_reject_")
)
async def reject_withdrawal(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "❌ Unauthorized.",
            show_alert=True
        )

        return

    withdrawal_id = callback.data.replace(
        "wd_reject_",
        "",
        1
    )

    withdrawal = await db.db.withdrawals.find_one({
        "withdrawal_id": withdrawal_id
    })

    if not withdrawal:

        await callback.answer(
            "❌ Withdrawal not found.",
            show_alert=True
        )

        return

    if withdrawal.get("status") != "pending":

        await callback.answer(
            "⚠️ This withdrawal is already processed.",
            show_alert=True
        )

        return

    user_id = int(
        withdrawal["user_id"]
    )

    amount_half = int(
        withdrawal.get(
            "amount_half_stars",
            0
        )
    )

    amount = format_stars(
        amount_half
    )

    now = datetime.now(timezone.utc)

    # ======================================================
    # ATOMIC STATUS CHANGE
    # ======================================================

    result = await db.db.withdrawals.update_one(
        {
            "withdrawal_id": withdrawal_id,
            "status": "pending"
        },
        {
            "$set": {
                "status": "rejected",

                "processed_at": now,

                "processed_by":
                    callback.from_user.id,

                "note":
                    "Withdrawal rejected"
            }
        }
    )

    if result.modified_count != 1:

        await callback.answer(
            "⚠️ Already processed.",
            show_alert=True
        )

        return

    # ======================================================
    # REFUND WALLET
    # ======================================================

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

    # ======================================================
    # UPDATE LEDGER
    # ======================================================

    await db.db.wallet_transactions.update_one(
        {
            "transaction_id":
                withdrawal_id
        },
        {
            "$set": {
                "status":
                    "refunded",

                "processed_at":
                    now,

                "processed_by":
                    callback.from_user.id
            }
        }
    )

    # Add refund ledger
    await db.db.wallet_transactions.insert_one({
        "transaction_id":
            f"REFUND_{withdrawal_id}",

        "user_id":
            user_id,

        "type":
            "withdrawal_refund",

        "amount_half_stars":
            amount_half,

        "status":
            "completed",

        "related_withdrawal":
            withdrawal_id,

        "created_at":
            now
    })

    # ======================================================
    # ADMIN MESSAGE
    # ======================================================

    await callback.message.edit_text(
        "❌ <b>Withdrawal Rejected</b>\n\n"

        f"🆔 <code>{withdrawal_id}</code>\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"⭐ Refunded: <b>{amount} Stars</b>\n\n"

        "The amount has been returned to "
        "the user's wallet.",
        parse_mode="HTML"
    )

    await callback.answer(
        "Withdrawal rejected and refunded."
    )

    # ======================================================
    # USER NOTIFICATION
    # ======================================================

    try:

        await callback.bot.send_message(
            user_id,

            "❌ <b>Withdrawal Rejected</b>\n\n"

            f"⭐ Amount refunded: "
            f"<b>{amount} Stars</b>\n"
            f"🆔 ID: <code>{withdrawal_id}</code>\n\n"

            "The amount has been returned "
            "to your wallet.",
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            "Could not notify user %s: %s",
            user_id,
            e
        )
