from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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
    admin_ids = getattr(settings, "ADMIN_IDS", [])

    if isinstance(admin_ids, int):
        admin_ids = [admin_ids]

    if isinstance(admin_ids, str):
        admin_ids = [
            int(x.strip())
            for x in admin_ids.split(",")
            if x.strip().isdigit()
        ]

    return user_id in admin_ids


# ==========================================================
# FORMAT STARS
# ==========================================================

def format_stars(half_stars: int) -> str:
    stars = half_stars / 2

    if stars.is_integer():
        return str(int(stars))

    return f"{stars:.1f}"


# ==========================================================
# /WITHDRAWALS
# ADMIN PENDING WITHDRAWAL LIST
# ==========================================================

@router.message(Command("withdrawals"))
async def admin_withdrawals(message: Message):

    admin_id = message.from_user.id

    if not is_admin(admin_id):
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
        .limit(30)
        .to_list(length=30)
    )

    if not withdrawals:
        await message.answer(
            "✅ <b>No pending withdrawals.</b>",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"💸 <b>Pending Withdrawals: "
        f"{len(withdrawals)}</b>",
        parse_mode="HTML"
    )

    for withdrawal in withdrawals:

        withdrawal_id = withdrawal.get(
            "withdrawal_id"
        )

        user_id = int(
            withdrawal.get(
                "user_id",
                0
            )
        )

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
            try:
                created_text = created_at.strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
            except Exception:
                created_text = "Unknown"
        else:
            created_text = "Unknown"

        text = (
            "💸 <b>Withdrawal Request</b>\n\n"

            f"👤 User ID:\n"
            f"<code>{user_id}</code>\n\n"

            f"⭐ Amount:\n"
            f"<b>{amount} Stars</b>\n\n"

            f"🆔 Withdrawal ID:\n"
            f"<code>{withdrawal_id}</code>\n\n"

            f"🕐 Created:\n"
            f"<code>{created_text}</code>\n\n"

            "⚠️ <b>Important:</b>\n"
            "First manually send the Stars to the user.\n"
            "Then press <b>I Have Paid</b>."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⭐ I Have Paid",
                        callback_data=(
                            f"wd_paid_{withdrawal_id}"
                        )
                    )
                ],
                [
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
# STEP 1
# ADMIN PRESSES "I HAVE PAID"
# ==========================================================

@router.callback_query(
    F.data.startswith("wd_paid_")
)
async def withdrawal_paid_step_one(
    callback: CallbackQuery
):

    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer(
            "❌ Unauthorized.",
            show_alert=True
        )
        return

    withdrawal_id = callback.data.replace(
        "wd_paid_",
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

    status = withdrawal.get("status")

    if status != "pending":
        await callback.answer(
            f"⚠️ Already processed: {status}",
            show_alert=True
        )
        return

    user_id = int(
        withdrawal.get(
            "user_id",
            0
        )
    )

    amount = int(
        withdrawal.get(
            "amount_stars",
            0
        )
    )

    # ======================================================
    # STEP 2 CONFIRMATION SCREEN
    # ======================================================

    text = (
        "⚠️ <b>Confirm Withdrawal Payment</b>\n\n"

        f"👤 User ID:\n"
        f"<code>{user_id}</code>\n\n"

        f"⭐ Amount:\n"
        f"<b>{amount} Stars</b>\n\n"

        f"🆔 Withdrawal ID:\n"
        f"<code>{withdrawal_id}</code>\n\n"

        "Have you <b>already manually sent</b> "
        f"<b>{amount} Stars</b> to this user?\n\n"

        "⚠️ Press <b>Yes, Approve</b> ONLY after "
        "you have actually sent the Stars."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Yes, Approve",
                    callback_data=(
                        f"wd_confirm_{withdrawal_id}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="↩️ Back",
                    callback_data=(
                        f"wd_back_{withdrawal_id}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=(
                        f"wd_reject_{withdrawal_id}"
                    )
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# BACK FROM CONFIRMATION
# ==========================================================

@router.callback_query(
    F.data.startswith("wd_back_")
)
async def withdrawal_back(
    callback: CallbackQuery
):

    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer(
            "❌ Unauthorized.",
            show_alert=True
        )
        return

    withdrawal_id = callback.data.replace(
        "wd_back_",
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
            "⚠️ This request is already processed.",
            show_alert=True
        )
        return

    user_id = int(
        withdrawal.get(
            "user_id",
            0
        )
    )

    amount = int(
        withdrawal.get(
            "amount_stars",
            0
        )
    )

    text = (
        "💸 <b>Withdrawal Request</b>\n\n"

        f"👤 User ID:\n"
        f"<code>{user_id}</code>\n\n"

        f"⭐ Amount:\n"
        f"<b>{amount} Stars</b>\n\n"

        f"🆔 Withdrawal ID:\n"
        f"<code>{withdrawal_id}</code>\n\n"

        "⚠️ First manually send the Stars "
        "to the user."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ I Have Paid",
                    callback_data=(
                        f"wd_paid_{withdrawal_id}"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=(
                        f"wd_reject_{withdrawal_id}"
                    )
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# FINAL APPROVAL
# ==========================================================

@router.callback_query(
    F.data.startswith("wd_confirm_")
)
async def withdrawal_final_approval(
    callback: CallbackQuery
):

    admin_id = callback.from_user.id

    if not is_admin(admin_id):
        await callback.answer(
            "❌ Unauthorized.",
            show_alert=True
        )
        return

    withdrawal_id = callback.data.replace(
        "wd_confirm_",
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

    # ======================================================
    # IMPORTANT:
    # ONLY PENDING REQUEST CAN BE APPROVED
    # ======================================================

    if withdrawal.get("status") != "pending":

        await callback.answer(
            "⚠️ This withdrawal has already been processed.",
            show_alert=True
        )

        return

    user_id = int(
        withdrawal.get(
            "user_id",
            0
        )
    )

    amount = int(
        withdrawal.get(
            "amount_stars",
            0
        )
    )

    amount_half = int(
        withdrawal.get(
            "amount_half_stars",
            amount * 2
        )
    )

    now = datetime.now(timezone.utc)

    # ======================================================
    # ATOMIC APPROVAL
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

                "processed_by": admin_id,

                "note": (
                    "Admin manually paid Stars "
                    "and confirmed payment."
                )
            }
        }
    )

    if result.modified_count != 1:

        await callback.answer(
            "⚠️ Already processed by another action.",
            show_alert=True
        )

        return

    # ======================================================
    # UPDATE WALLET LEDGER
    # ======================================================

    await db.db.wallet_transactions.update_one(
        {
            "transaction_id": withdrawal_id
        },
        {
            "$set": {
                "status": "paid",

                "processed_at": now,

                "processed_by": admin_id
            }
        }
    )

    # ======================================================
    # ADMIN SCREEN
    # ======================================================

    await callback.message.edit_text(
        "✅ <b>Withdrawal Approved</b>\n\n"

        f"👤 User: <code>{user_id}</code>\n"
        f"⭐ Amount: <b>{amount} Stars</b>\n"
        f"🆔 ID: <code>{withdrawal_id}</code>\n\n"

        "📌 Status: <b>PAID</b>\n\n"

        "The admin confirmed that the Stars "
        "were manually sent to the user.",
        parse_mode="HTML"
    )

    await callback.answer(
        "✅ Withdrawal marked as PAID."
    )

    # ======================================================
    # USER NOTIFICATION
    # ======================================================

    try:

        await callback.bot.send_message(
            user_id,

            "🎉 <b>Withdrawal Completed</b>\n\n"

            f"⭐ Amount: <b>{amount} Stars</b>\n"
            f"🆔 ID: <code>{withdrawal_id}</code>\n\n"

            "Your withdrawal has been approved "
            "by the admin.",
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            "Failed to notify user %s: %s",
            user_id,
            e
        )


# ==========================================================
# REJECT WITHDRAWAL
# ==========================================================

@router.callback_query(
    F.data.startswith("wd_reject_")
)
async def withdrawal_reject(
    callback: CallbackQuery
):

    admin_id = callback.from_user.id

    if not is_admin(admin_id):
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
        withdrawal.get(
            "user_id",
            0
        )
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
    # ATOMIC REJECTION
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

                "processed_by": admin_id,

                "note": "Withdrawal rejected by admin."
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
    # REFUND USER WALLET
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
    # UPDATE ORIGINAL LEDGER
    # ======================================================

    await db.db.wallet_transactions.update_one(
        {
            "transaction_id":
                withdrawal_id
        },
        {
            "$set": {
                "status": "refunded",

                "processed_at": now,

                "processed_by": admin_id
            }
        }
    )

    # ======================================================
    # REFUND LEDGER
    # ======================================================

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

        f"👤 User: <code>{user_id}</code>\n"
        f"⭐ Refunded: <b>{amount} Stars</b>\n"
        f"🆔 ID: <code>{withdrawal_id}</code>\n\n"

        "The Stars have been returned "
        "to the user's wallet.",
        parse_mode="HTML"
    )

    await callback.answer(
        "❌ Rejected and refunded."
    )

    # ======================================================
    # USER NOTIFICATION
    # ======================================================

    try:

        await callback.bot.send_message(
            user_id,

            "❌ <b>Withdrawal Rejected</b>\n\n"

            f"⭐ Refunded: <b>{amount} Stars</b>\n"
            f"🆔 ID: <code>{withdrawal_id}</code>\n\n"

            "The amount has been returned "
            "to your wallet.",
            parse_mode="HTML"
        )

    except Exception as e:

        logger.warning(
            "Failed to notify user %s: %s",
            user_id,
            e
        )
