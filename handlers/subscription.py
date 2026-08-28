from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import db
from services.api_keys import APIKeyService
from datetime import datetime, timezone
from handlers.start import get_main_menu_keyboard
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.payment import PaymentService

router = Router()

@router.message(Command("mystats"))
async def cmd_mystats(message: Message):
    await show_user_stats(message.from_user.id, message)

@router.callback_query(F.data == "menu_mystats")
async def callback_mystats(callback: CallbackQuery):
    await show_user_stats(callback.from_user.id, callback.message, edit=True)
    await callback.answer()

async def show_user_stats(user_id: int, message: Message, edit: bool = False):
    key_doc = await APIKeyService.get_active_key_info(user_id)
    
    if not key_doc:
        text = "📊 You have no active subscription stats. Purchase a plan via /plans."
    else:
        used = key_doc['requests_used']
        limit = key_doc['request_limit']
        remaining = max(0, limit - used)
        expires = key_doc['expires_at'].strftime('%Y-%m-%d %H:%M:%S UTC')
        
        text = (
            f"📊 <b>Your API Usage Statistics:</b>\n\n"
            f"💎 Plan: <code>{key_doc['plan_id'].upper()}</code>\n"
            f"📈 Requests Used: <code>{used}</code>\n"
            f"📉 Requests Remaining: <code>{remaining}</code>\n"
            f"⏳ Expiry: <code>{expires}</code>\n"
            f"🔒 API Key Status: <b>{key_doc['status'].upper()}</b>"
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu_home")]])
    if edit:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.message(Command("renew"))
async def cmd_renew(message: Message):
    await message.answer("To renew or upgrade your subscription, please click below:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 View Plans", callback_data="menu_plans")]]))

@router.callback_query(F.data == "menu_renew")
async def callback_renew(callback: CallbackQuery):
    await callback.message.edit_text("To renew or upgrade your subscription, please select below:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 View Plans", callback_data="menu_plans")]]))
    await callback.answer()

@router.message(Command("docs"))
async def cmd_docs(message: Message):
    await message.answer(
        f"📚 <b>API Documentation & Guide</b>\n\n"
        f"Base URL: <code>{settings.API_BASE_URL}</code>\n\n"
        f"<b>Endpoint:</b>\n<code>GET /download?url=VIDEO_ID&type=audio&api_key=YOUR_KEY</code>\n"
        f"<code>GET /download?url=VIDEO_ID&type=video&api_key=YOUR_KEY</code>\n\n"
        f"Visit <code>{settings.API_BASE_URL}/docs</code> for full details.",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "menu_docs")
async def callback_docs(callback: CallbackQuery):
    await callback.message.edit_text(
        f"📚 <b>API Documentation & Guide</b>\n\n"
        f"Base URL: <code>{settings.API_BASE_URL}</code>\n\n"
        f"<b>Endpoint:</b>\n<code>GET /download?url=VIDEO_ID&type=audio&api_key=YOUR_KEY</code>\n"
        f"<code>GET /download?url=VIDEO_ID&type=video&api_key=YOUR_KEY</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Menu", callback_data="menu_home")]]),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(Command("support"))
async def cmd_support(message: Message):
    await message.answer(
        f"🆘 <b>Support Center</b>\n\n"
        f"Need help? Contact our support channel or group:\n"
        f"Channel: {settings.SUPPORT_CHANNEL}\n"
        f"Group: {settings.SUPPORT_GROUP}",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "menu_support")
async def callback_support(callback: CallbackQuery):
    await callback.message.edit_text(
        f"🆘 <b>Support Center</b>\n\n"
        f"Need help? Contact our support channel or group:\n"
        f"Channel: {settings.SUPPORT_CHANNEL}\n"
        f"Group: {settings.SUPPORT_GROUP}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Menu", callback_data="menu_home")]]),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("buy_plan_"))
async def callback_buy_plan(callback: CallbackQuery):
    plan_id = callback.data.replace("buy_plan_", "")
    user_id = callback.from_user.id

    try:
        payment_info = await PaymentService.create_payment_order(user_id, plan_id)
        
        # In production, send real gateway invoice link. Here we provide a mock pay button for demonstration.
        text = (
            f"🛒 <b>Payment Order Created</b>\n\n"
            f"Plan: <code>{plan_id.upper()}</code>\n"
            f"Amount: <code>{payment_info['amount']} {payment_info['currency']}</code>\n"
            f"Payment ID: <code>{payment_info['payment_id']}</code>\n\n"
            f"<i>Click below to complete your secure payment.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Pay Now (Mock Gateway)", url=payment_info["checkout_url"])],
            [InlineKeyboardButton(text="✅ Simulate Successful Payment", callback_data=f"sim_pay_{payment_info['payment_id']}")],
            [InlineKeyboardButton(text="🔙 Back to Plans", callback_data="menu_plans")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"Error creating order: {str(e)}", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("sim_pay_"))
async def callback_simulate_payment(callback: CallbackQuery):
    payment_id = callback.data.replace("sim_pay_", "")
    transaction_id = f"TXN_MOCK_{uuid.uuid4().hex[:8].upper()}"
    
    success = await PaymentService.verify_and_fulfill_payment(payment_id, transaction_id)
    if success:
        key_doc = await APIKeyService.get_active_key_info(callback.from_user.id)
        text = (
            f"🎉 <b>Payment Successful & Verified!</b>\n\n"
            f"Your subscription is now active.\n"
            f"You can view your API key via <b>🔑 My API Key</b> in the menu."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu_home")]])
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.answer("Payment verification failed or already processed.", show_alert=True)
        
