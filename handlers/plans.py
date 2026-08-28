from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command

from database import db


router = Router()


# ==========================================
# DEFAULT PLANS
# ==========================================

DEFAULT_PLANS = [
    {
        "plan_id": "7days",
        "name": "7 Days",
        "price": 49,
        "duration_days": 7,
        "status": "active"
    },
    {
        "plan_id": "30days",
        "name": "30 Days",
        "price": 149,
        "duration_days": 30,
        "status": "active"
    },
    {
        "plan_id": "90days",
        "name": "90 Days",
        "price": 349,
        "duration_days": 90,
        "status": "active"
    },
    {
        "plan_id": "365days",
        "name": "365 Days",
        "price": 999,
        "duration_days": 365,
        "status": "active"
    }
]


# ==========================================
# GET PLANS KEYBOARD
# ==========================================

async def get_plans_keyboard():

    plans = []

    try:
        cursor = db.db.plans.find({
            "status": "active"
        })

        plans = await cursor.to_list(length=10)

    except Exception as e:
        print(f"Plans database error: {e}")

    # --------------------------------------
    # If MongoDB has no plans
    # use default plans
    # --------------------------------------

    if not plans:
        plans = DEFAULT_PLANS

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

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )


# ==========================================
# /PLANS
# ==========================================

@router.message(Command("plans"))
async def cmd_plans(message: Message):

    keyboard = await get_plans_keyboard()

    await message.answer(
        "<b>💎 Music API Plans</b>\n\n"
        "Choose your plan:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ==========================================
# MENU → PLANS
# ==========================================

@router.callback_query(
    F.data == "menu_plans"
)
async def callback_plans(
    callback: CallbackQuery
):

    keyboard = await get_plans_keyboard()

    await callback.message.edit_text(
        "<b>💎 Music API Plans</b>\n\n"
        "Choose your plan:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()
