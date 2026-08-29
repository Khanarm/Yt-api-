import uuid
from datetime import datetime, timezone, timedelta

from aiogram.types import LabeledPrice

from database import db
from services.api_keys import APIKeyService
from utils.logger import logger


class PaymentService:
    """
    Payment system:
    1. Telegram Stars (XTR)
    2. Referral Wallet Stars

    INR / Razorpay / UPI payment is NOT used.
    """

    # ==========================================================
    # TELEGRAM STARS PAYMENT
    # ==========================================================

    @staticmethod
    async def create_payment_order(user_id: int, plan_id: str) -> dict:
        plan = await db.db.plans.find_one({
            "plan_id": plan_id,
            "status": "active"
        })

        if not plan:
            raise ValueError("Invalid or inactive plan.")

        amount = int(plan.get("price", 0))

        if amount <= 0:
            raise ValueError("Invalid plan Stars price.")

        payment_id = (
            f"STAR_{uuid.uuid4().hex[:16].upper()}"
        )

        payload = f"{payment_id}:{plan_id}"

        now = datetime.now(timezone.utc)

        await db.db.payments.insert_one({
            "payment_id": payment_id,
            "user_id": user_id,
            "plan_id": plan_id,

            "amount": amount,
            "currency": "XTR",

            "provider": "telegram_stars",
            "status": "pending",

            "payload": payload,

            "created_at": now,
            "expires_at": now + timedelta(minutes=30),

            "verified_at": None,
            "transaction_id": None,

            "telegram_payment_charge_id": None,
            "provider_payment_charge_id": None
        })

        return {
            "payment_id": payment_id,
            "payload": payload,
            "amount": amount,
            "currency": "XTR",

            "prices": [
                LabeledPrice(
                    label=plan["name"],
                    amount=amount
                )
            ]
        }

    @staticmethod
    async def get_payment_by_payload(payload: str):
        return await db.db.payments.find_one({
            "payload": payload
        })

    @staticmethod
    async def fulfill_stars_payment(
        payment_id: str,
        user_id: int,
        currency: str,
        total_amount: int,
        telegram_payment_charge_id: str,
        provider_payment_charge_id=None
    ) -> dict:

        payment = await db.db.payments.find_one({
            "payment_id": payment_id,
            "user_id": user_id
        })

        if not payment:
            return {
                "success": False,
                "message": "Payment order not found."
            }

        # Already processed
        if payment.get("status") == "completed":
            return {
                "success": True,
                "already_completed": True,
                "api_key": None
            }

        if payment.get("status") != "pending":
            return {
                "success": False,
                "message": "Payment is no longer pending."
            }

        # Currency check
        if currency != "XTR":
            return {
                "success": False,
                "message": "Invalid payment currency."
            }

        # Amount check
        if int(total_amount) != int(payment["amount"]):

            logger.error(
                "Stars amount mismatch | payment=%s required=%s paid=%s",
                payment_id,
                payment["amount"],
                total_amount
            )

            return {
                "success": False,
                "message": "Payment amount mismatch."
            }

        # ======================================================
        # DUPLICATE TELEGRAM CHARGE PROTECTION
        # ======================================================

        duplicate = await db.db.payments.find_one({
            "telegram_payment_charge_id":
                telegram_payment_charge_id,
            "status": "completed"
        })

        if duplicate:

            if duplicate.get("user_id") == user_id:
                return {
                    "success": True,
                    "already_completed": True,
                    "api_key": None
                }

            return {
                "success": False,
                "message": "This payment has already been used."
            }

        # ======================================================
        # MARK PAYMENT COMPLETED
        # ======================================================

        now = datetime.now(timezone.utc)

        result = await db.db.payments.update_one(
            {
                "payment_id": payment_id,
                "user_id": user_id,
                "status": "pending"
            },
            {
                "$set": {
                    "status": "completed",
                    "verified_at": now,

                    "transaction_id":
                        telegram_payment_charge_id,

                    "telegram_payment_charge_id":
                        telegram_payment_charge_id,

                    "provider_payment_charge_id":
                        provider_payment_charge_id,

                    "amount_paid":
                        int(total_amount)
                }
            }
        )

        if result.modified_count != 1:
            return {
                "success": False,
                "message": "Payment was already processed."
            }

        # ======================================================
        # ACTIVATE SUBSCRIPTION
        # ======================================================

        try:

            raw_key = await (
                PaymentService
                ._activate_subscription_benefits(
                    user_id,
                    payment["plan_id"]
                )
            )

        except Exception as e:

            logger.error(
                "Subscription activation failed "
                "after Stars payment %s: %s",
                payment_id,
                e,
                exc_info=True
            )

            return {
                "success": False,
                "message": (
                    "Payment received, but subscription "
                    "activation failed. Contact support."
                )
            }

        return {
            "success": True,
            "already_completed": False,
            "api_key": raw_key,

            "payment_id": payment_id,

            "amount": int(total_amount),

            "telegram_payment_charge_id":
                telegram_payment_charge_id
        }

    # ==========================================================
    # PAY FROM REFERRAL WALLET
    # ==========================================================

    @staticmethod
    async def pay_with_wallet(
        user_id: int,
        plan_id: str
    ) -> dict:

        plan = await db.db.plans.find_one({
            "plan_id": plan_id,
            "status": "active"
        })

        if not plan:
            return {
                "success": False,
                "message": "Invalid or inactive plan."
            }

        amount = int(plan.get("price", 0))

        if amount <= 0:
            return {
                "success": False,
                "message": "Invalid plan price."
            }

        # ------------------------------------------------------
        # Wallet uses half-Star units.
        #
        # 1 unit = 0.5 Star
        #
        # Example:
        # 10 units = 5 Stars
        # 100 units = 50 Stars
        # ------------------------------------------------------

        amount_half_stars = amount * 2

        payment_id = (
            f"WALLET_{uuid.uuid4().hex[:16].upper()}"
        )

        now = datetime.now(timezone.utc)

        # Create wallet payment record
        await db.db.payments.insert_one({
            "payment_id": payment_id,

            "user_id": user_id,
            "plan_id": plan_id,

            "amount": amount,
            "currency": "XTR",

            "provider": "referral_wallet",
            "status": "pending",

            "payload": payment_id,

            "created_at": now,
            "verified_at": None,

            "transaction_id": None
        })

        # ======================================================
        # ATOMIC WALLET DEDUCTION
        # ======================================================

        result = await db.db.users.update_one(
            {
                "user_id": user_id,

                "wallet_half_stars": {
                    "$gte": amount_half_stars
                }
            },
            {
                "$inc": {
                    "wallet_half_stars":
                        -amount_half_stars
                }
            }
        )

        if result.modified_count != 1:

            await db.db.payments.update_one(
                {
                    "payment_id": payment_id
                },
                {
                    "$set": {
                        "status": "failed",
                        "failure_reason":
                            "insufficient_wallet"
                    }
                }
            )

            return {
                "success": False,
                "message": (
                    f"Insufficient wallet balance. "
                    f"You need {amount} Stars."
                )
            }

        # ======================================================
        # ACTIVATE SUBSCRIPTION
        # ======================================================

        try:

            raw_key = await (
                PaymentService
                ._activate_subscription_benefits(
                    user_id,
                    plan_id
                )
            )

        except Exception as e:

            # Refund wallet
            await db.db.users.update_one(
                {
                    "user_id": user_id
                },
                {
                    "$inc": {
                        "wallet_half_stars":
                            amount_half_stars
                    }
                }
            )

            await db.db.payments.update_one(
                {
                    "payment_id": payment_id
                },
                {
                    "$set": {
                        "status": "failed",
                        "failure_reason":
                            "activation_failed",
                        "error": str(e)
                    }
                }
            )

            logger.error(
                "Wallet purchase activation failed | "
                "payment=%s user=%s error=%s",
                payment_id,
                user_id,
                e,
                exc_info=True
            )

            return {
                "success": False,
                "message": (
                    "Subscription activation failed. "
                    "Your wallet was refunded."
                )
            }

        # ======================================================
        # MARK WALLET PAYMENT COMPLETED
        # ======================================================

        await db.db.payments.update_one(
            {
                "payment_id": payment_id,
                "status": "pending"
            },
            {
                "$set": {
                    "status": "completed",
                    "verified_at":
                        datetime.now(timezone.utc),

                    "transaction_id":
                        payment_id,

                    "amount_paid": amount
                }
            }
        )

        # ======================================================
        # WALLET LEDGER
        # ======================================================

        await db.db.wallet_transactions.insert_one({
            "transaction_id": payment_id,

            "user_id": user_id,

            "type": "plan_purchase",

            "amount_half_stars":
                -amount_half_stars,

            "plan_id": plan_id,

            "created_at":
                datetime.now(timezone.utc)
        })

        return {
            "success": True,

            "payment_id": payment_id,

            "amount": amount,

            "api_key": raw_key
        }

    # ==========================================================
    # SUBSCRIPTION ACTIVATION
    # ==========================================================

    @staticmethod
    async def _activate_subscription_benefits(
        user_id: int,
        plan_id: str
    ):

        plan = await db.db.plans.find_one({
            "plan_id": plan_id
        })

        if not plan:
            raise ValueError(
                f"Plan {plan_id} not found."
            )

        duration_days = int(
            plan["duration_days"]
        )

        request_limit = int(
            plan.get("request_limit", 0)
        )

        if request_limit <= 0:
            raise ValueError(
                f"Invalid request limit for "
                f"plan {plan_id}."
            )

        now = datetime.now(timezone.utc)

        expires_at = (
            now +
            timedelta(days=duration_days)
        )

        # ------------------------------------------------------
        # Activate subscription
        # ------------------------------------------------------

        await db.db.subscriptions.update_one(
            {
                "user_id": user_id
            },
            {
                "$set": {
                    "plan_id": plan_id,

                    "status": "active",

                    "expires_at": expires_at,

                    "updated_at": now
                },

                "$setOnInsert": {
                    "created_at": now
                }
            },
            upsert=True
        )

        # ------------------------------------------------------
        # Generate API key
        # ------------------------------------------------------

        raw_key = await APIKeyService.create_api_key(
            user_id=user_id,
            plan_id=plan_id,
            request_limit=request_limit,
            expires_at=expires_at
        )

        return raw_key
