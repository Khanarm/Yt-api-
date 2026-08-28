from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from database import db
from services.api_keys import APIKeyService
from handlers.start import get_main_menu_keyboard
from datetime import datetime, timezone

router = Router()

@router.message(Command("mykey"))
async def cmd_mykey(message: Message):
    await show_user_key(message.from_user.id, message)

@router.callback_query(F.data == "menu_mykey")
async def callback_mykey(callback: CallbackQuery):
    await show_user_key(callback.from_user.id, callback.message, edit=True)
    await callback.answer()

async def show_user_key(user_id: int, message: Message, edit: bool = False):
    key_doc = await APIKeyService.get_active_key_info(user_id)
    
    if not key_doc:
        text = "❌ You don't have an active API key. Please purchase a plan using /plans."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 View Plans", callback_data="menu_plans"), InlineKeyboardButton(text="🔙 Menu", callback_data="menu_home")]])
    else:
        # Note: Raw key cannot be recovered if it's already hashed in DB. 
        # We display the prefix or give an option to regenerate/view if tracked temporarily.
        text = (
            f"🔑 <b>Your Active API Key Info:</b>\n\n"
            f"Prefix: <code>{key_doc['key_prefix']}...</code>\n"
            f"Status: <b>{key_doc['status'].upper()}</b>\n"
            f"Plan ID: <code>{key_doc['plan_id']}</code>\n"
            f"Requests Used: <code>{key_doc['requests_used']} / {key_doc['request_limit']}</code>\n"
            f"Expires At: <code>{key_doc['expires_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}</code>\n\n"
            f"<i>If you lost your full key, you can regenerate it below.</i>"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Regenerate Key", callback_data="regenerate_key")],
            [InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu_home")]
        ])

    if edit:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "regenerate_key")
async def callback_regenerate(callback: CallbackQuery):
    user_id = callback.from_user.id
    active_key = await APIKeyService.get_active_key_info(user_id)
    
    if not active_key:
        await callback.answer("No active subscription/key found to regenerate.", show_alert=True)
        return

    # Generate new key using existing plan parameters and expiry
    raw_key = await APIKeyService.create_api_key(
        user_id=user_id,
        plan_id=active_key["plan_id"],
        request_limit=active_key["request_limit"],
        expires_at=active_key["expires_at"]
    )

    text = (
        f"⚠️ <b>API Key Regenerated Successfully!</b>\n\n"
        f"Your new API Key:\n<code>{raw_key}</code>\n\n"
        f"<i>Save this key securely. It will not be shown again in full format!</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Menu", callback_data="menu_home")]])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("API key regenerated!")
