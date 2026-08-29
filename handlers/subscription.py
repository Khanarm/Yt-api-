from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery
)
from aiogram.filters import Command
from datetime import datetime, timezone

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
        key_doc = await APIKeyService.get_active_key_info(user_id)

    except Exception as e:

        logger.error(
            f"Failed to get API stats for user={user_id}: {e}",
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

        used = int(key_doc.get("requests_used", 0))
        limit = int(key_doc.get("request_limit", 0))

        remaining = max(0, limit - used)

        expires_at = key_doc.get("expires_at")

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
            f"💎 Plan: <code>{plan_id.upper()}</code>\n"
            f"📈 Used: <code>{used}</code>\n"
            f"📉 Remaining: <code>{remaining}</code>\n"
            f"📊 Limit: <code>{limit}</code>\n"
            f"⏳ Expiry: <code>{expires}</code>\n"
            f"🔒 Status: <b>{status.upper()}</b>"
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


# ==========================================================
# PLAN SELECTED
# ==========================================================

@router.callback_query(
    F.data.startswith("buy_plan_")
)
async def select_payment_method(
    callback: CallbackQuery
):

    plan_id = callback.data.replace(
        "buy_plan_",
        "",
        1
    )

    plan = await db.db.plans.find_one({
        "plan_id": plan_id,
        "status": "active"
    })

    if not plan:

        await callback.answer(
            "❌ Plan not found.",
            show_alert=True
        )

        return

    price = int(plan.get("price", 0))
    name = str(plan.get("name", "Plan"))

    if price <= 0:

        await callback.answer(
            "❌ Invalid plan price.",
            show_alert=True
        )

        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"⭐ Pay {price} Stars",
                    callback_data=f"pay_stars_{plan_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Pay from Wallet",
                    callback_data=f"pay_wallet_{plan_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Back to Plans",
                    callback_data="payment_back_plans"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "💳 <b>Choose Payment Method</b>\n\n"
        f"💎 Plan: <b>{name}</b>\n"
        f"⭐ Price: <b>{price} Stars</b>\n\n"
        "Choose how you want to pay:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# PAY WITH TELEGRAM STARS
# ==========================================================

@router.callback_query(
    F.data.startswith("pay_stars_")
)
async def pay_with_stars(
    callback: CallbackQuery
):

    plan_id = callback.data.replace(
        "pay_stars_",
        "",
        1
    )

    user_id = callback.from_user.id

    try:

        order = await PaymentService.create_payment_order(
            user_id=user_id,
            plan_id=plan_id
        )

        await callback.message.answer_invoice(
            title="Music API Subscription",
            description=(
                f"Purchase {plan_id} API subscription"
            ),
            payload=order["payload"],
            currency="XTR",
            prices=order["prices"]
        )

        await callback.answer()

    except Exception as e:

        logger.error(
            f"Stars invoice creation failed "
            f"user={user_id}: {e}",
            exc_info=True
        )

        await callback.answer(
            "❌ Unable to create Stars payment.",
            show_alert=True
        )


# ==========================================================
# PRE-CHECKOUT
# ==========================================================

@router.pre_checkout_query()
async def process_pre_checkout(
    query: PreCheckoutQuery
):

    try:

        payment = await PaymentService.get_payment_by_payload(
            query.invoice_payload
        )

        if not payment:

            await query.answer(
                ok=False,
                error_message=(
                    "Payment order not found. "
                    "Please create a new payment."
                )
            )

            return

        if payment.get("status") != "pending":

            await query.answer(
                ok=False,
                error_message=(
                    "This payment order is no longer valid."
                )
            )

            return

        if query.currency != "XTR":

            await query.answer(
                ok=False,
                error_message="Invalid payment currency."
            )

            return

        expected_amount = int(
            payment.get("amount", 0)
        )

        if int(query.total_amount) != expected_amount:

            await query.answer(
                ok=False,
                error_message=(
                    "Payment amount does not match "
                    "the selected plan."
                )
            )

            return

        await query.answer(ok=True)

    except Exception as e:

        logger.error(
            f"Pre-checkout error: {e}",
            exc_info=True
        )

        await query.answer(
            ok=False,
            error_message=(
                "Unable to verify payment. "
                "Please try again."
            )
        )


# ==========================================================
# SUCCESSFUL TELEGRAM STARS PAYMENT
# ==========================================================

@router.message(
    F.successful_payment
)
async def successful_stars_payment(
    message: Message
):

    payment = message.successful_payment

    if not payment:

        return

    user_id = message.from_user.id

    payload = payment.invoice_payload

    try:

        payment_doc = await PaymentService.get_payment_by_payload(
            payload
        )

        if not payment_doc:

            await message.answer(
                "❌ Payment received but order was not found.\n\n"
                "Please contact support."
            )

            return

        result = await PaymentService.fulfill_stars_payment(
            payment_id=payment_doc["payment_id"],

            user_id=user_id,

            currency=payment.currency,

            total_amount=payment.total_amount,

            telegram_payment_charge_id=(
                payment.telegram_payment_charge_id
            ),

            provider_payment_charge_id=(
                payment.provider_payment_charge_id
            )
        )

        if not result.get("success"):

            await message.answer(
                "❌ <b>Payment verification failed</b>\n\n"
                f"{result.get('message', 'Unknown error')}\n\n"
                "Please contact support.",
                parse_mode="HTML"
            )

            return

        raw_key = result.get("api_key")

        if raw_key:

            await message.answer(
                "🎉 <b>Payment Successful!</b>\n\n"
                f"⭐ Paid: "
                f"<b>{payment.total_amount} Stars</b>\n\n"
                "✅ Your subscription is now active.\n\n"
                "🔑 <b>Your API Key:</b>\n"
                f"<code>{raw_key}</code>\n\n"
                "⚠️ Save this API key securely. "
                "It will not be shown again.",
                parse_mode="HTML"
            )

        else:

            await message.answer(
                "✅ <b>Payment already processed.</b>\n\n"
                "Your subscription is active.",
                parse_mode="HTML"
            )

    except Exception as e:

        logger.error(
            f"Successful Stars payment handling failed "
            f"user={user_id}: {e}",
            exc_info=True
        )

        await message.answer(
            "⚠️ <b>Payment received</b>\n\n"
            "There was a problem activating your subscription.\n"
            "Please contact support.",
            parse_mode="HTML"
        )


# ==========================================================
# PAY FROM WALLET
# ==========================================================

@router.callback_query(
    F.data.startswith("pay_wallet_")
)
async def pay_from_wallet(
    callback: CallbackQuery
):

    plan_id = callback.data.replace(
        "pay_wallet_",
        "",
        1
    )

    user_id = callback.from_user.id

    plan = await db.db.plans.find_one({
        "plan_id": plan_id,
        "status": "active"
    })

    if not plan:

        await callback.answer(
            "❌ Plan not found.",
            show_alert=True
        )

        return

    price = int(plan.get("price", 0))

    if price <= 0:

        await callback.answer(
            "❌ Invalid plan price.",
            show_alert=True
        )

        return

    user = await db.db.users.find_one({
        "user_id": user_id
    })

    wallet_half_stars = int(
        (user or {}).get(
            "wallet_half_stars",
            0
        )
    )

    wallet_stars = wallet_half_stars / 2

    if wallet_half_stars < price * 2:

        await callback.answer(
            (
                f"❌ Insufficient wallet balance.\n\n"
                f"Your balance: {wallet_stars:g} ⭐\n"
                f"Required: {price} ⭐"
            ),
            show_alert=True
        )

        return

    # ------------------------------------------------------
    # Confirmation screen
    # ------------------------------------------------------

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Confirm - {price} ⭐",
                    callback_data=f"confirm_wallet_{plan_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data=f"buy_plan_{plan_id}"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "💰 <b>Wallet Payment</b>\n\n"
        f"💎 Plan: <b>{plan.get('name', plan_id)}</b>\n"
        f"💵 Price: <b>{price} Stars</b>\n"
        f"💰 Your wallet: <b>{wallet_stars:g} Stars</b>\n\n"
        f"After purchase: "
        f"<b>{wallet_stars - price:g} Stars</b>\n\n"
        "Confirm wallet payment?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# CONFIRM WALLET PAYMENT
# ==========================================================

@router.callback_query(
    F.data.startswith("confirm_wallet_")
)
async def confirm_wallet_payment(
    callback: CallbackQuery
):

    plan_id = callback.data.replace(
        "confirm_wallet_",
        "",
        1
    )

    user_id = callback.from_user.id

    await callback.answer(
        "⏳ Processing wallet payment..."
    )

    try:

        result = await PaymentService.pay_with_wallet(
            user_id=user_id,
            plan_id=plan_id
        )

        if not result.get("success"):

            await callback.message.edit_text(
                "❌ <b>Wallet Payment Failed</b>\n\n"
                f"{result.get('message', 'Unknown error')}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🔙 Back to Plans",
                                callback_data="menu_plans"
                            )
                        ]
                    ]
                )
            )

            return

        raw_key = result.get("api_key")

        if raw_key:

            await callback.message.edit_text(
                "🎉 <b>Purchase Successful!</b>\n\n"
                f"💰 Paid from wallet: "
                f"<b>{result['amount']} Stars</b>\n\n"
                "✅ Subscription activated.\n\n"
                "🔑 <b>Your API Key:</b>\n"
                f"<code>{raw_key}</code>\n\n"
                "⚠️ Save this API key securely. "
                "It will not be shown again.",
                parse_mode="HTML"
            )

        else:

            await callback.message.edit_text(
                "✅ <b>Purchase Successful!</b>\n\n"
                "Your subscription is active.",
                parse_mode="HTML"
            )

    except Exception as e:

        logger.error(
            f"Wallet payment failed "
            f"user={user_id}: {e}",
            exc_info=True
        )

        await callback.message.edit_text(
            "❌ <b>Wallet Payment Error</b>\n\n"
            "Your wallet was not intentionally charged "
            "if the subscription could not be activated.\n\n"
            "Please try again.",
            parse_mode="HTML"
        )


# ==========================================================
# PAYMENT BACK TO PLANS
# ==========================================================

@router.callback_query(
    F.data == "payment_back_plans"
)
async def payment_back_plans(
    callback: CallbackQuery
):

    from handlers.plans import get_plans_keyboard

    keyboard = await get_plans_keyboard()

    await callback.message.edit_text(
        "💎 <b>Music API Plans</b>\n\n"
        "Choose your plan (Telegram Stars):",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()
