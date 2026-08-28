from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from services.api_keys import APIKeyService
from services.payment import PaymentService
from config import settings


router = Router()


class PaymentStates(StatesGroup):
    waiting_for_utr = State()


# ==========================================
# MY STATS
# ==========================================

@router.message(Command("mystats"))
async def cmd_mystats(message: Message):
    await show_user_stats(
        message.from_user.id,
        message
    )


@router.callback_query(F.data == "menu_mystats")
async def callback_mystats(callback: CallbackQuery):
    await show_user_stats(
        callback.from_user.id,
        callback.message,
        edit=True
    )
    await callback.answer()


async def show_user_stats(
    user_id: int,
    message: Message,
    edit: bool = False
):

    key_doc = await APIKeyService.get_active_key_info(
        user_id
    )

    if not key_doc:
        text = (
            "📊 <b>No Active Subscription</b>\n\n"
            "Purchase a plan using /plans."
        )

    else:
        used = key_doc["requests_used"]
        limit = key_doc["request_limit"]

        remaining = max(
            0,
            limit - used
        )

        expires = key_doc[
            "expires_at"
        ].strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        text = (
            "📊 <b>Your API Usage</b>\n\n"
            f"💎 Plan: "
            f"<code>{key_doc['plan_id'].upper()}</code>\n"
            f"📈 Used: <code>{used}</code>\n"
            f"📉 Remaining: <code>{remaining}</code>\n"
            f"⏳ Expiry: <code>{expires}</code>\n"
            f"🔒 Status: "
            f"<b>{key_doc['status'].upper()}</b>"
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


# ==========================================
# RENEW
# ==========================================

@router.message(Command("renew"))
async def cmd_renew(message: Message):

    await message.answer(
        "💎 Select a plan to renew or upgrade:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 View Plans",
                        callback_data="menu_plans"
                    )
                ]
            ]
        )
    )


@router.callback_query(F.data == "menu_renew")
async def callback_renew(callback: CallbackQuery):

    await callback.message.edit_text(
        "💎 Select a plan to renew or upgrade:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 View Plans",
                        callback_data="menu_plans"
                    )
                ]
            ]
        )
    )

    await callback.answer()


# ==========================================
# DOCUMENTATION
# ==========================================

@router.message(Command("docs"))
async def cmd_docs(message: Message):

    await message.answer(
        f"📚 <b>Music API Documentation</b>\n\n"
        f"Base URL:\n"
        f"<code>{settings.API_BASE_URL}</code>\n\n"

        f"<b>Audio</b>\n"
        f"<code>"
        f"{settings.API_BASE_URL}"
        f"/download?url=VIDEO_ID"
        f"&type=audio"
        f"&api_key=YOUR_KEY"
        f"</code>\n\n"

        f"<b>Video</b>\n"
        f"<code>"
        f"{settings.API_BASE_URL}"
        f"/download?url=VIDEO_ID"
        f"&type=video"
        f"&api_key=YOUR_KEY"
        f"</code>",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu_docs")
async def callback_docs(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        f"📚 <b>Music API Documentation</b>\n\n"
        f"Base URL:\n"
        f"<code>{settings.API_BASE_URL}</code>\n\n"

        f"<b>Audio:</b>\n"
        f"<code>"
        f"{settings.API_BASE_URL}"
        f"/download?url=VIDEO_ID"
        f"&type=audio"
        f"&api_key=YOUR_KEY"
        f"</code>\n\n"

        f"<b>Video:</b>\n"
        f"<code>"
        f"{settings.API_BASE_URL}"
        f"/download?url=VIDEO_ID"
        f"&type=video"
        f"&api_key=YOUR_KEY"
        f"</code>",

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


# ==========================================
# SUPPORT
# ==========================================

@router.message(Command("support"))
async def cmd_support(message: Message):

    await message.answer(
        f"🆘 <b>Support Center</b>\n\n"
        f"Channel: {settings.SUPPORT_CHANNEL}\n"
        f"Group: {settings.SUPPORT_GROUP}",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu_support")
async def callback_support(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        f"🆘 <b>Support Center</b>\n\n"
        f"Channel: {settings.SUPPORT_CHANNEL}\n"
        f"Group: {settings.SUPPORT_GROUP}",

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


# ==========================================
# BUY PLAN
# ==========================================

@router.callback_query(
    F.data.startswith("buy_plan_")
)
async def callback_buy_plan(
    callback: CallbackQuery
):

    plan_id = callback.data.replace(
        "buy_plan_",
        "",
        1
    )

    user_id = callback.from_user.id

    await callback.answer(
        "Creating secure payment QR..."
    )

    try:

        payment_info = (
            await PaymentService.create_payment_order(
                user_id,
                plan_id
            )
        )

        caption = (
            "💳 <b>Payment Required</b>\n\n"
            f"💰 Amount: "
            f"<b>₹{payment_info['amount']}</b>\n\n"

            "📱 Scan the QR code using "
            "any supported UPI app.\n\n"

            "1️⃣ Scan QR\n"
            "2️⃣ Pay the exact amount\n"
            "3️⃣ Tap <b>Verify Payment</b>\n"
            "4️⃣ Send your UTR / UPI Transaction ID\n\n"

            "⚠️ This QR is for this payment only.\n"
            "⏱ QR expires in about 30 minutes."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
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

        await callback.message.answer_photo(
            photo=payment_info["image_url"],
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:

        await callback.message.answer(
            "❌ <b>Unable to create payment QR.</b>\n\n"
            "Please try again later.",
            parse_mode="HTML"
        )


# ==========================================
# VERIFY BUTTON
# ==========================================

@router.callback_query(
    F.data.startswith("verify_payment_")
)
async def callback_verify_payment(
    callback: CallbackQuery,
    state: FSMContext
):

    payment_id = callback.data.replace(
        "verify_payment_",
        "",
        1
    )

    user_id = callback.from_user.id

    payment = await db.db.payments.find_one({
        "payment_id": payment_id,
        "user_id": user_id,
        "status": "pending"
    })

    if not payment:

        await callback.answer(
            "Payment order not found or already processed.",
            show_alert=True
        )

        return

    # Store payment ID in FSM
    await state.update_data(
        payment_id=payment_id
    )

    await state.set_state(
        PaymentStates.waiting_for_utr
    )

    await callback.message.answer(
        "🔎 <b>Payment Verification</b>\n\n"
        "Please send the <b>UTR / UPI Transaction ID</b> "
        "you received after payment.\n\n"
        "Example:\n"
        "<code>123456789012</code>\n\n"
        "⚠️ Do not send your UPI PIN or password.",
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================
# UTR MESSAGE
# ==========================================

@router.message(
    PaymentStates.waiting_for_utr
)
async def receive_utr(
    message: Message,
    state: FSMContext
):

    utr = (
        message.text or ""
    ).strip()

    if not utr:

        await message.answer(
            "❌ Please send a valid UTR / "
            "UPI Transaction ID."
        )

        return

    # Basic length protection
    if len(utr) < 6 or len(utr) > 40:

        await message.answer(
            "❌ Invalid UTR format.\n\n"
            "Please check your payment receipt "
            "and send the correct UTR."
        )

        return

    data = await state.get_data()

    payment_id = data.get(
        "payment_id"
    )

    if not payment_id:

        await state.clear()

        await message.answer(
            "❌ Payment session expired. "
            "Please create a new payment from /plans."
        )

        return

    await message.answer(
        "🔎 Checking your payment with Razorpay..."
    )

    try:

        result = (
            await PaymentService
            .verify_and_fulfill_payment(
                payment_id=payment_id,
                user_id=message.from_user.id,
                utr=utr
            )
        )

    except Exception:

        await message.answer(
            "❌ Payment verification service "
            "temporarily unavailable.\n\n"
            "Please try again."
        )

        return

    if not result.get("success"):

        await message.answer(
            "❌ <b>Payment Not Verified</b>\n\n"
            f"{result.get('message', 'Payment not found.')}\n\n"
            "If you have just paid, wait a little and "
            "try the same UTR again.",
            parse_mode="HTML"
        )

        return

    # Very important:
    # Raw API key is shown only now.
    raw_key = result.get("api_key")

    await state.clear()

    await message.answer(
        "🎉 <b>Payment Successful!</b>\n\n"
        "✅ Subscription activated.\n"
        "🔑 Your API key has been generated.\n\n"

        "<b>YOUR API KEY:</b>\n"
        f"<code>{raw_key}</code>\n\n"

        "⚠️ <b>Save this key now.</b>\n"
        "For security, the complete key will not "
        "be stored in the database.",
        parse_mode="HTML"
    )
