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


async def get_plans_keyboard():

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

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )


@router.message(Command("plans"))
async def cmd_plans(message: Message):

    keyboard = await get_plans_keyboard()

    await message.answer(
        "<b>💎 Music API Plans</b>\n\n"
        "Choose your plan:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


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
