from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from datetime import timezone

from database import db
from services.api_keys import APIKeyService
from services.payment import PaymentService
from config import settings
from utils.logger import logger


router = Router()


# ==========================================================
# MY STATS
# ==========================================================

@router.message(Command("mystats"))
async def cmd_mystats(message: Message):

    await show_user_stats(
        user_id=message.from_user.id,
        message=message
    )


@router.callback_query(F.data == "menu_mystats")
async def callback_mystats(callback: CallbackQuery):

    await show_user_stats(
        user_id=callback.from_user.id,
        message=callback.message,
        edit=True
    )

    await callback.answer()


async def show_user_stats(
    user_id: int,
    message: Message,
    edit: bool = False
):

    try:
        key_doc = await APIKeyService.get_active_key_info(
            user_id
        )

    except Exception as e:

        logger.error(
            f"Failed to get API stats for "
            f"user={user_id}: {e}",
            exc_info=True
        )

        text = (
            "❌ <b>Unable to load your stats.</b>\n\n"
            "Please try again later."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Back to Menu",
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

        return

    if not key_doc:

        text = (
            "📊 <b>No Active Subscription</b>\n\n"
            "You don't have an active API subscription.\n\n"
            "Purchase a plan to get your API key."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 View Plans",
                        callback_data="menu_plans"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Back to Menu",
                        callback_data="menu_home"
                    )
                ]
            ]
        )

    else:

        used = int(
            key_doc.get(
                "requests_used",
                0
            )
        )

        limit = int(
            key_doc.get(
                "request_limit",
                0
            )
        )

        remaining = max(
            0,
            limit - used
        )

        expires_at = key_doc.get(
            "expires_at"
        )

        if expires_at:

            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(
                    tzinfo=timezone.utc
                )

            expires = expires_at.strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )

        else:

            expires = "Unknown"

        plan_id = str(
            key_doc.get(
                "plan_id",
                "unknown"
            )
        )

        status = str(
            key_doc.get(
                "status",
                "unknown"
            )
        )

        text = (
            "📊 <b>Your API Usage</b>\n\n"
            f"💎 Plan: "
            f"<code>{plan_id.upper()}</code>\n"
            f"📈 Used: "
            f"<code>{used}</code>\n"
            f"📉 Remaining: "
            f"<code>{remaining}</code>\n"
            f"📊 Limit: "
            f"<code>{limit}</code>\n"
            f"⏳ Expiry: "
            f"<code>{expires}</code>\n"
            f"🔒 Status: "
            f"<b>{status.upper()}</b>"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔄 Renew / Upgrade",
                        callback_data="menu_renew"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Back to Menu",
                        callback_data="menu_home"
                    )
                ]
            ]
        )

    if edit:

        try:

            await message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        except Exception as e:

            logger.warning(
                f"Could not edit stats message: {e}"
            )

    else:

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# ==========================================================
# RENEW
# ==========================================================

@router.message(Command("renew"))
async def cmd_renew(message: Message):

    await message.answer(
        "💎 <b>Renew / Upgrade</b>\n\n"
        "Choose a plan:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 View Plans",
                        callback_data="menu_plans"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Back to Menu",
                        callback_data="menu_home"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu_renew")
async def callback_renew(callback: CallbackQuery):

    await callback.message.edit_text(
        "💎 <b>Renew / Upgrade</b>\n\n"
        "Choose a plan:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 View Plans",
                        callback_data="menu_plans"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Back to Menu",
                        callback_data="menu_home"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# DOCUMENTATION
# ==========================================================

@router.message(Command("docs"))
async def cmd_docs(message: Message):

    await message.answer(
        f"📚 <b>Music API Documentation</b>\n\n"
        f"<b>Base URL:</b>\n"
        f"<code>{settings.API_BASE_URL}</code>\n\n"
        f"<b>🎵 Audio:</b>\n"
        f"<code>"
        f"{settings.API_BASE_URL}"
        f"/download?url=VIDEO_ID"
        f"&type=audio"
        f"&api_key=YOUR_KEY"
        f"</code>\n\n"
        f"<b>🎬 Video:</b>\n"
        f"<code>"
        f"{settings.API_BASE_URL}"
        f"/download?url=VIDEO_ID"
        f"&type=video"
        f"&api_key=YOUR_KEY"
        f"</code>\n\n"
        "🔐 Keep your API key private.",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu_docs")
async def callback_docs(callback: CallbackQuery):

    await callback.message.edit_text(
        f"📚 <b>Music API Documentation</b>\n\n"
        f"<b>Base URL:</b>\n"
        f"<code>{settings.API_BASE_URL}</code>\n\n"
        f"<b>🎵 Audio:</b>\n"
        f"<code>"
        f"{settings.API_BASE_URL}"
        f"/download?url=VIDEO_ID"
        f"&type=audio"
        f"&api_key=YOUR_KEY"
        f"</code>\n\n"
        f"<b>🎬 Video:</b>\n"
        f"<code>"
        f"{settings.API_BASE_URL}"
        f"/download?url=VIDEO_ID"
        f"&type=video"
        f"&api_key=YOUR_KEY"
        f"</code>\n\n"
        "🔐 Keep your API key private.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Menu",
                        callback_data="menu_home"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# SUPPORT
# ==========================================================

@router.message(Command("support"))
async def cmd_support(message: Message):

    await message.answer(
        f"🆘 <b>Support Center</b>\n\n"
        f"📢 Channel:\n"
        f"{settings.SUPPORT_CHANNEL}\n\n"
        f"👥 Group:\n"
        f"{settings.SUPPORT_GROUP}",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu_support")
async def callback_support(callback: CallbackQuery):

    await callback.message.edit_text(
        f"🆘 <b>Support Center</b>\n\n"
        f"📢 Channel:\n"
        f"{settings.SUPPORT_CHANNEL}\n\n"
        f"👥 Group:\n"
        f"{settings.SUPPORT_GROUP}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Menu",
                        callback_data="menu_home"
                    )
                ]
            ]
        ),
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# BUY PLAN
# ==========================================================

@router.callback_query(
    F.data.startswith("buy_plan_")
)
async def callback_buy_plan(callback: CallbackQuery):

    plan_id = callback.data.replace(
        "buy_plan_",
        "",
        1
    )

    user_id = callback.from_user.id

    await callback.answer(
        "Creating payment link..."
    )

    try:

        plan = await db.db.plans.find_one({
            "plan_id": plan_id,
            "status": "active"
        })

        if not plan:

            await callback.message.answer(
                "❌ <b>Plan not found.</b>\n\n"
                "Please open /plans again.",
                parse_mode="HTML"
            )

            return

        payment_info = (
            await PaymentService.create_payment_order(
                user_id=user_id,
                plan_id=plan_id
            )
        )

        payment_url = payment_info.get(
            "payment_url"
        )

        if not payment_url:
            raise ValueError(
                "Payment URL was not returned."
            )

        amount = payment_info.get(
            "amount",
            plan["price"]
        )

        text = (
            "💳 <b>Payment Required</b>\n\n"
            f"💎 Plan: "
            f"<b>{plan['name']}</b>\n"
            f"💰 Amount: "
            f"<b>₹{amount}</b>\n\n"
            "👇 Tap <b>Pay Now</b> to complete "
            "your payment.\n\n"
            "After completing the payment, "
            "come back here and tap "
            "<b>Verify Payment</b>.\n\n"
            "⚠️ Please pay the exact amount.\n"
            "⏱ Payment link expires in about 30 minutes."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"💳 Pay ₹{amount}",
                        url=payment_url
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Verify Payment",
                        callback_data=(
                            f"verify_payment_"
                            f"{payment_info['payment_id']}"
                        )
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Back to Plans",
                        callback_data="menu_plans"
                    )
                ]
            ]
        )

        await callback.message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:

        logger.error(
            f"Payment Link creation failed | "
            f"user={user_id} | "
            f"plan={plan_id} | "
            f"error={e}",
            exc_info=True
        )

        await callback.message.answer(
            "❌ <b>Unable to create payment link.</b>\n\n"
            "Please try again later.",
            parse_mode="HTML"
        )


# ==========================================================
# VERIFY PAYMENT
# ==========================================================

@router.callback_query(
    F.data.startswith("verify_payment_")
)
async def callback_verify_payment(
    callback: CallbackQuery
):

    payment_id = callback.data.replace(
        "verify_payment_",
        "",
        1
    )

    user_id = callback.from_user.id

    await callback.answer(
        "Checking payment..."
    )

    payment = await db.db.payments.find_one({
        "payment_id": payment_id,
        "user_id": user_id,
        "status": "pending"
    })

    if not payment:

        completed = await db.db.payments.find_one({
            "payment_id": payment_id,
            "user_id": user_id,
            "status": "completed"
        })

        if completed:

            await callback.message.answer(
                "✅ <b>This payment is already verified.</b>\n\n"
                "If you already received your API key, "
                "you can use it normally.",
                parse_mode="HTML"
            )

        else:

            await callback.message.answer(
                "❌ <b>Payment order not found.</b>\n\n"
                "Please create a new payment from /plans.",
                parse_mode="HTML"
            )

        return

    checking_message = await callback.message.answer(
        "🔎 <b>Checking payment with Razorpay...</b>\n\n"
        "Please wait...",
        parse_mode="HTML"
    )

    try:

        result = await PaymentService.verify_and_fulfill_payment(
            payment_id=payment_id,
            user_id=user_id
        )

    except Exception as e:

        logger.error(
            f"Payment verification failed | "
            f"payment={payment_id} | "
            f"user={user_id} | "
            f"error={e}",
            exc_info=True
        )

        await checking_message.edit_text(
            "❌ <b>Payment verification failed.</b>\n\n"
            "Razorpay could not be contacted right now.\n"
            "Please try again after a few seconds.",
            parse_mode="HTML"
        )

        return

    # ------------------------------------------------------
    # PAYMENT NOT VERIFIED
    # ------------------------------------------------------

    if not result.get("success"):

        error_message = result.get(
            "message",
            "Payment has not been received yet."
        )

        await checking_message.edit_text(
            "❌ <b>Payment Not Verified</b>\n\n"
            f"{error_message}\n\n"
            "If you have just completed the payment, "
            "wait a few seconds and press "
            "<b>Verify Payment</b> again.",
            parse_mode="HTML"
        )

        return

    # ------------------------------------------------------
    # ALREADY COMPLETED
    # ------------------------------------------------------

    if result.get("already_completed"):

        await checking_message.edit_text(
            "✅ <b>Payment Already Verified</b>\n\n"
            "Your subscription has already been activated.\n\n"
            "Use /mystats to check your API status.",
            parse_mode="HTML"
        )

        return

    # ------------------------------------------------------
    # GET API KEY
    # ------------------------------------------------------

    raw_key = result.get(
        "api_key"
    )

    if not raw_key:

        logger.error(
            f"Payment completed but API key missing | "
            f"payment={payment_id} | "
            f"user={user_id}"
        )

        await checking_message.edit_text(
            "✅ <b>Payment Received</b>\n\n"
            "Your payment was successful, but "
            "the API key could not be generated automatically.\n\n"
            "Please contact support.",
            parse_mode="HTML"
        )

        return

    # ------------------------------------------------------
    # SUCCESS
    # ------------------------------------------------------

    await checking_message.edit_text(
        "🎉 <b>Payment Successful!</b>\n\n"
        "✅ Subscription activated.\n"
        "🔑 Your API key has been generated.\n\n"
        "<b>YOUR API KEY:</b>\n"
        f"<code>{raw_key}</code>\n\n"
        "⚠️ <b>Important:</b>\n"
        "Save this API key somewhere safe.\n\n"
        "🔐 Do not share your API key publicly.",
        parse_mode="HTML"
    )

    logger.info(
        f"Subscription successfully activated | "
        f"user={user_id} | "
        f"payment={payment_id}"
    )


# ==========================================================
# BACKUP: SHOW PLANS FROM PAYMENT SCREEN
# ==========================================================

@router.callback_query(
    F.data == "payment_back_plans"
)
async def payment_back_plans(
    callback: CallbackQuery
):

    cursor = db.db.plans.find({
        "status": "active"
    })

    plans = await cursor.to_list(
        length=10
    )

    keyboard = []

    for plan in plans:

        keyboard.append([
            InlineKeyboardButton(
                text=(
                    f"💎 {plan['name']} - "
                    f"₹{plan['price']} / "
                    f"{plan['duration_days']} Days"
                ),
                callback_data=(
                    f"buy_plan_{plan['plan_id']}"
                )
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Back to Menu",
            callback_data="menu_home"
        )
    ])

    await callback.message.edit_text(
        "<b>💎 Music API Plans</b>\n\n"
        "Choose your plan:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        ),
        parse_mode="HTML"
    )

    await callback.answer()
