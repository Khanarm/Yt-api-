from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from datetime import datetime, timezone
from database import db
from config import settings
from services.api_keys import APIKeyService
from services.payment import PaymentService

router = Router()

def is_owner(user_id: int) -> bool:
    return user_id == settings.OWNER_ID

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Users & Stats", callback_data="admin_stats"),
            InlineKeyboardButton(text="💎 Plans", callback_data="admin_plans")
        ],
        [
            InlineKeyboardButton(text="🔑 API Keys", callback_data="admin_keys"),
            InlineKeyboardButton(text="💰 Payments", callback_data="admin_payments")
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton(text="🔍 Search User", callback_data="admin_search_prompt")
        ],
        [
            InlineKeyboardButton(text="🔙 Exit Admin", callback_data="menu_home")
        ]
    ])

@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("❌ You are not authorized to use the admin panel.")
        return

    await message.answer(
        "🛠 <b>Admin Control Panel</b>\nSelect an operation below:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_menu")
async def callback_admin_menu(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    await callback.message.edit_text(
        "🛠 <b>Admin Control Panel</b>\nSelect an operation below:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    total_users = await db.db.users.count_documents({})
    active_subs = await db.db.subscriptions.count_documents({"status": "active"})
    expired_subs = await db.db.subscriptions.count_documents({"status": "expired"})
    total_keys = await db.db.api_keys.count_documents({})
    active_keys = await db.db.api_keys.count_documents({"status": "active"})
    
    total_requests = await db.db.api_usage.count_documents({})
    
    # Today's requests
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    todays_requests = await db.db.api_usage.count_documents({"timestamp": {"$gte": start_of_day}})
    
    total_payments = await db.db.payments.count_documents({"status": "completed"})
    
    # Today's revenue calculation
    pipeline = [
        {"$match": {"status": "completed", "verified_at": {"$gte": start_of_day}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    revenue_cursor = db.db.payments.aggregate(pipeline)
    revenue_result = await revenue_cursor.to_list(length=1)
    todays_revenue = revenue_result[0]["total"] if revenue_result else 0.0

    stats_text = (
        f"📊 <b>System Statistics Dashboard</b>\n\n"
        f"👥 Total Users: <code>{total_users}</code>\n"
        f"💎 Active Subscribers: <code>{active_subs}</code>\n"
        f"⏳ Expired Subscribers: <code>{expired_subs}</code>\n"
        f"🔑 Total API Keys: <code>{total_keys}</code> (Active: <code>{active_keys}</code>)\n\n"
        f"📈 Total API Requests: <code>{total_requests}</code>\n"
        f"📅 Today's Requests: <code>{todays_requests}</code>\n"
        f"💰 Completed Payments: <code>{total_payments}</code>\n"
        f"💵 Today's Revenue: <code>{todays_revenue}</code>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_menu")]])
    await callback.message.edit_text(stats_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(Command("user"))
async def cmd_user_lookup(message: Message):
    if not is_owner(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("Usage: <code>/user USER_ID</code>", parse_mode="HTML")
        return

    try:
        target_user_id = int(args[1])
    except ValueError:
        await message.answer("Invalid User ID format.")
        return

    user_doc = await db.db.users.find_one({"user_id": target_user_id})
    if not user_doc:
        await message.answer("❌ User not found in database.")
        return

    key_doc = await APIKeyService.get_active_key_info(target_user_id)
    sub_doc = await db.db.subscriptions.find_one({"user_id": target_user_id})

    status = key_doc["status"].upper() if key_doc else "NONE"
    plan_id = key_doc["plan_id"] if key_doc else (sub_doc["plan_id"] if sub_doc else "NONE")
    expiry = key_doc["expires_at"].strftime('%Y-%m-%d %H:%M:%S UTC') if key_doc else "N/A"
    used = key_doc["requests_used"] if key_doc else 0
    limit = key_doc["request_limit"] if key_doc else 0
    remaining = max(0, limit - used)

    text = (
        f"👤 <b>User Details:</b> <code>{target_user_id}</code>\n"
        f"Username: @{user_doc.get('username', 'N/A')}\n"
        f"Plan: <code>{plan_id.upper()}</code>\n"
        f"API Key Status: <b>{status}</b>\n"
        f"Subscription Expiry: <code>{expiry}</code>\n"
        f"Requests Used: <code>{used}</code>\n"
        f"Requests Remaining: <code>{remaining}</code>"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔒 Revoke Key", callback_data=f"adm_rev_{target_user_id}"),
            InlineKeyboardButton(text="♻️ Reset Key", callback_data=f"adm_reg_{target_user_id}")
        ],
        [InlineKeyboardButton(text="🔙 Admin Menu", callback_data="admin_menu")]
    ])
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_rev_"))
async def callback_admin_revoke(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    target_user_id = int(callback.data.replace("adm_rev_", ""))
    await APIKeyService.revoke_user_keys(target_user_id)
    await callback.answer(f"API keys revoked for user {target_user_id}.", show_alert=True)

@router.callback_query(F.data.startswith("adm_reg_"))
async def callback_admin_regenerate(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    target_user_id = int(callback.data.replace("adm_reg_", ""))
    key_doc = await APIKeyService.get_active_key_info(target_user_id)
    if not key_doc:
        await callback.answer("No active key/plan found to regenerate.", show_alert=True)
        return

    await APIKeyService.create_api_key(
        user_id=target_user_id,
        plan_id=key_doc["plan_id"],
        request_limit=key_doc["request_limit"],
        expires_at=key_doc["expires_at"]
    )
    await callback.answer(f"New API key generated for user {target_user_id}.", show_alert=True)
