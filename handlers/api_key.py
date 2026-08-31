from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command

from services.api_keys import APIKeyService

router = Router()


# ==========================================================
# /MYKEY
# ==========================================================

@router.message(Command("mykey"))
async def cmd_mykey(message: Message):
    await show_user_key(
        user_id=message.from_user.id,
        message=message,
        edit=False,
    )


# ==========================================================
# MY API KEY BUTTON
# ==========================================================

@router.callback_query(F.data == "menu_mykey")
async def callback_mykey(callback: CallbackQuery):

    await show_user_key(
        user_id=callback.from_user.id,
        message=callback.message,
        edit=True,
    )

    await callback.answer()


# ==========================================================
# SHOW ACTIVE PURCHASED API KEY
# ==========================================================

async def show_user_key(
    user_id: int,
    message: Message,
    edit: bool = False,
):

    # IMPORTANT:
    # This only reads the existing active key.
    # It NEVER generates a new key.
    key_doc = await APIKeyService.get_active_key_info(user_id)

    # ======================================================
    # NO ACTIVE KEY
    # ======================================================

    if not key_doc:

        text = (
            "🔑 <b>My API Key</b>\n\n"
            "❌ <b>No active API key found.</b>\n\n"
            "Purchase a plan to get your API key."
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💎 Buy API",
                        callback_data="menu_plans",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Main Menu",
                        callback_data="menu_home",
                    )
                ],
            ]
        )

    # ======================================================
    # ACTIVE KEY
    # ======================================================

    else:

        # Get the SAME purchased key.
        api_key = APIKeyService.get_display_key(key_doc)

        request_limit = int(
            key_doc.get("request_limit", 0)
        )

        requests_used = int(
            key_doc.get("requests_used", 0)
        )

        # Unlimited plan
        if request_limit == -1:
            limit_text = "Unlimited"
            usage_text = f"{requests_used:,} / Unlimited"

        else:
            limit_text = f"{request_limit:,}"
            usage_text = (
                f"{requests_used:,} / {limit_text}"
            )

        # ==================================================
        # EXPIRY
        # ==================================================

        expires_at = key_doc.get("expires_at")

        if expires_at:

            if expires_at.tzinfo is None:
                expires_text = expires_at.strftime(
                    "%d-%m-%Y %H:%M UTC"
                )
            else:
                expires_text = expires_at.strftime(
                    "%d-%m-%Y %H:%M UTC"
                )

        else:
            expires_text = "N/A"

        # ==================================================
        # API KEY
        # ==================================================

        if api_key:

            key_text = (
                f"<code>{api_key}</code>"
            )

        else:

            key_text = (
                "❌ <i>This old key cannot be displayed.</i>\n"
                "Please purchase a new plan to get a "
                "securely viewable API key."
            )

        # ==================================================
        # MESSAGE
        # ==================================================

        text = (
            "🔑 <b>My API Key</b>\n\n"

            "🔐 <b>Your Purchased API Key:</b>\n"
            f"{key_text}\n\n"

            f"📦 <b>Plan:</b> "
            f"<code>{key_doc.get('plan_id', 'N/A')}</code>\n"

            f"📊 <b>Requests Used:</b> "
            f"<code>{usage_text}</code>\n"

            f"📅 <b>Expires:</b> "
            f"<code>{expires_text}</code>\n"

            f"🟢 <b>Status:</b> "
            f"<code>{str(key_doc.get('status', 'active')).upper()}</code>\n\n"

            "⚠️ <b>Keep your API key private.</b>\n"
            "Do not share it with anyone.\n\n"

            "ℹ️ Opening this page does NOT generate a new key "
            "and does NOT reset your request usage."
        )

        # IMPORTANT:
        # No Generate Key button.
        # No Regenerate Key button.
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Main Menu",
                        callback_data="menu_home",
                    )
                ]
            ]
        )

    # ======================================================
    # SEND / EDIT
    # ======================================================

    if edit:

        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    else:

        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
