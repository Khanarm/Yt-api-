from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command

from database import db
from utils.logger import logger


router = Router()


# ==========================================================
# DEFAULT PLANS
# ==========================================================

DEFAULT_PLANS = [
    {
        "plan_id": "7days",
        "name": "7 Days",
        "price": 49,
        "duration_days": 7,
        "request_limit": 1000,
        "status": "active"
    },
    {
        "plan_id": "30days",
        "name": "30 Days",
        "price": 149,
        "duration_days": 30,
        "request_limit": 5000,
        "status": "active"
    },
    {
        "plan_id": "90days",
        "name": "90 Days",
        "price": 349,
        "duration_days": 90,
        "request_limit": 15000,
        "status": "active"
    },
    {
        "plan_id": "365days",
        "name": "365 Days",
        "price": 999,
        "duration_days": 365,
        "request_limit": 50000,
        "status": "active"
    }
]


# ==========================================================
# ENSURE DEFAULT PLANS EXIST IN MONGODB
# ==========================================================

async def ensure_default_plans():
    """
    Make sure all default plans exist in MongoDB.

    Existing plans are NOT deleted.
    Existing custom values are preserved.
    Missing default plans are automatically created.
    """

    try:

        for default_plan in DEFAULT_PLANS:

            existing = await db.db.plans.find_one({
                "plan_id": default_plan["plan_id"]
            })

            if not existing:

                await db.db.plans.insert_one(
                    default_plan.copy()
                )

                logger.info(
                    f"Created default plan: "
                    f"{default_plan['plan_id']}"
                )

            else:

                # --------------------------------------------------
                # Repair missing fields only
                # --------------------------------------------------

                update_fields = {}

                if "name" not in existing:
                    update_fields["name"] = default_plan["name"]

                if "price" not in existing:
                    update_fields["price"] = default_plan["price"]

                if "duration_days" not in existing:
                    update_fields["duration_days"] = (
                        default_plan["duration_days"]
                    )

                if "request_limit" not in existing:
                    update_fields["request_limit"] = (
                        default_plan["request_limit"]
                    )

                if "status" not in existing:
                    update_fields["status"] = "active"

                if update_fields:

                    await db.db.plans.update_one(
                        {
                            "plan_id":
                                default_plan["plan_id"]
                        },
                        {
                            "$set": update_fields
                        }
                    )

                    logger.info(
                        f"Repaired plan: "
                        f"{default_plan['plan_id']} | "
                        f"fields={list(update_fields.keys())}"
                    )

    except Exception as e:

        logger.error(
            f"Failed to ensure default plans: {e}",
            exc_info=True
        )


# ==========================================================
# GET ACTIVE PLANS
# ==========================================================

async def get_active_plans():

    try:

        # First make sure plans exist
        await ensure_default_plans()

        cursor = db.db.plans.find(
            {
                "status": "active"
            }
        ).sort(
            "duration_days",
            1
        )

        plans = await cursor.to_list(
            length=20
        )

        return plans

    except Exception as e:

        logger.error(
            f"Failed to load plans: {e}",
            exc_info=True
        )

        return []


# ==========================================================
# GET PLANS KEYBOARD
# ==========================================================

async def get_plans_keyboard():

    plans = await get_active_plans()

    keyboard = []

    for plan in plans:

        plan_id = str(
            plan.get(
                "plan_id",
                ""
            )
        )

        name = str(
            plan.get(
                "name",
                "Plan"
            )
        )

        price = int(
            plan.get(
                "price",
                0
            )
        )

        duration_days = int(
            plan.get(
                "duration_days",
                0
            )
        )

        # ------------------------------------------
        # Ignore broken plans
        # ------------------------------------------

        if not plan_id:
            continue

        if price <= 0:
            continue

        if duration_days <= 0:
            continue

        keyboard.append([
            InlineKeyboardButton(
                text=(
                    f"💎 {name} - "
                    f"₹{price} / "
                    f"{duration_days} Days"
                ),
                callback_data=(
                    f"buy_plan_{plan_id}"
                )
            )
        ])

    # ------------------------------------------
    # Back button
    # ------------------------------------------

    keyboard.append([
        InlineKeyboardButton(
            text="🔙 Back to Menu",
            callback_data="menu_home"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )


# ==========================================================
# /PLANS
# ==========================================================

@router.message(
    Command("plans")
)
async def cmd_plans(
    message: Message
):

    keyboard = await get_plans_keyboard()

    # ------------------------------------------
    # Check if plans available
    # ------------------------------------------

    if len(keyboard.inline_keyboard) <= 1:

        await message.answer(
            "❌ <b>No plans are available right now.</b>\n\n"
            "Please try again later.",
            parse_mode="HTML"
        )

        return

    await message.answer(
        "💎 <b>Music API Plans</b>\n\n"
        "Choose your plan:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ==========================================================
# MENU → PLANS
# ==========================================================

@router.callback_query(
    F.data == "menu_plans"
)
async def callback_plans(
    callback: CallbackQuery
):

    keyboard = await get_plans_keyboard()

    # ------------------------------------------
    # Check if plans available
    # ------------------------------------------

    if len(keyboard.inline_keyboard) <= 1:

        await callback.message.edit_text(
            "❌ <b>No plans are available right now.</b>\n\n"
            "Please try again later.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
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

        return

    await callback.message.edit_text(
        "💎 <b>Music API Plans</b>\n\n"
        "Choose your plan:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()


# ==========================================================
# BACKUP → PLANS
# ==========================================================

@router.callback_query(
    F.data == "payment_back_plans"
)
async def payment_back_plans(
    callback: CallbackQuery
):

    keyboard = await get_plans_keyboard()

    await callback.message.edit_text(
        "💎 <b>Music API Plans</b>\n\n"
        "Choose your plan:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()
