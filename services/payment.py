import uuid
from datetime import datetime, timezone, timedelta
from database import db
from services.api_keys import APIKeyService
from config import settings
from utils.logger import logger

class PaymentService:
    @staticmethod
    async def create_payment_order(user_id: int, plan_id: str) -> dict:
        """Creates a pending payment order for a specific plan."""
        plan = await db.db.plans.find_one({"plan_id": plan_id, "status": "active"})
        if not plan:
            raise ValueError("Invalid or inactive plan selected.")

        payment_id = f"PAY_{uuid.uuid4().hex[:12].upper()}"
        
        payment_doc = {
            "payment_id": payment_id,
            "user_id": user_id,
            "plan_id": plan_id,
            "amount": plan["price"],
            "currency": plan["currency"],
            "status": "pending",
            "provider": settings.PAYMENT_PROVIDER,
            "created_at": datetime.now(timezone.utc),
            "verified_at": None,
            "transaction_id": None
        }

        await db.db.payments.insert_one(payment_doc)
        logger.info(f"Created payment order {payment_id} for user {user_id} and plan {plan_id}.")
        
        # Return payment details along with a checkout/pay link mockup depending on provider
        return {
            "payment_id": payment_id,
            "amount": plan["price"],
            "currency": plan["currency"],
            "checkout_url": f"https://payment-gateway.example.com/pay/{payment_id}" # Mock gateway link
        }

    @staticmethod
    async def verify_and_fulfill_payment(payment_id: str, transaction_id: str) -> bool:
        """Server-side verification of payment, preventing duplicate processing."""
        payment = await db.db.payments.find_one({"payment_id": payment_id})
        
        if not payment:
            logger.warning(f"Payment verification failed: Payment ID {payment_id} not found.")
            return False

        if payment["status"] == "completed":
            logger.info(f"Payment ID {payment_id} was already processed successfully (duplicate prevention).")
            return True

        if payment["status"] != "pending":
            logger.warning(f"Payment ID {payment_id} is in invalid state: {payment['status']}")
            return False

        # Mark payment as completed atomically
        update_result = await db.db.payments.update_one(
            {"payment_id": payment_id, "status": "pending"},
            {
                "$set": {
                    "status": "completed",
                    "verified_at": datetime.now(timezone.utc),
                    "transaction_id": transaction_id
                }
            }
        )

        if update_result.modified_count == 0:
            return False

        # Fulfill subscription and generate API key
        await PaymentService._activate_subscription_benefits(payment["user_id"], payment["plan_id"])
        return True

    @staticmethod
    async def _activate_subscription_benefits(user_id: int, plan_id: str):
        plan = await db.db.plans.find_one({"plan_id": plan_id})
        if not plan:
            logger.error(f"Plan {plan_id} not found during subscription activation for user {user_id}.")
            return

        duration_days = plan["duration_days"]
        request_limit = plan["request_limit"]
        expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)

        # Upsert subscription record
        await db.db.subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "plan_id": plan_id,
                    "status": "active",
                    "expires_at": expires_at,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$setOnInsert": {
                    "created_at": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )

        # Generate new API key
        raw_key = await APIKeyService.create_api_key(
            user_id=user_id,
            plan_id=plan_id,
            request_limit=request_limit,
            expires_at=expires_at
        )

        logger.info(f"Successfully activated subscription and API key for user {user_id} under plan {plan_id}.")
        return raw_key
