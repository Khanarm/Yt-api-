from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from datetime import datetime, timezone
from database import db
from config import settings

router = Router()

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Plans", callback_data="menu_plans"),
            InlineKeyboardButton(text="🔑 My API Key", callback_data="menu_mykey")
        ],
        [
            InlineKeyboardButton(text="📊 My Stats", callback_data="menu_mystats"),
            InlineKeyboardButton(text="🔄 Renew", callback_data="menu_renew")
        ],
        [
            InlineKeyboardButton(text="📚 API Docs", callback_data="menu_docs"),
            InlineKeyboardButton(text="🆘 Support", callback_data="menu_support")
        ]
    ])

@router.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Register user if not exists
    await db.db.users.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username": username,
                "last_active": datetime.now(timezone.utc)
            },
            "$setOnInsert": {
                "created_at": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )

    welcome_text = (
        f"👋 Welcome, <b>{message.from_user.first_name}</b>!\n\n"
        "This is the official Subscription & API Key Management Bot for your Music Bot system.\n"
        "Use the buttons below to browse plans, manage your API key, or check your statistics."
    )
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

@router.callback_query(F.data == "menu_home")
async def callback_home(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏠 Main Menu:\nSelect an option below:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()
