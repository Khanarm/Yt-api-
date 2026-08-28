import uuid
from datetime import datetime, timezone, timedelta

import httpx

from database import db
from services.api_keys import APIKeyService
from config import settings
from utils.logger import logger


RAZORPAY_API_URL = "https://api.razorpay.com/v1"


class PaymentService:

    @staticmethod
    def _check_config():
        if settings.PAYMENT_PROVIDER.lower() != "razorpay":
            raise ValueError(
                "PAYMENT_PROVIDER must be set to razorpay."
            )

        if not settings.PAYMENT_API_KEY:
            raise ValueError(
                "PAYMENT_API_KEY is not configured."
            )

        if not settings.PAYMENT_SECRET:
            raise ValueError(
                "PAYMENT_SECRET is not configured."
            )

    @staticmethod
    async def _request(method: str, endpoint: str, **kwargs):
        PaymentService._check_config()

        url = f"{RAZORPAY_API_URL}{endpoint}"

        async with httpx.AsyncClient(
            timeout=30.0,
            auth=(
                settings.PAYMENT_API_KEY,
                settings.PAYMENT_SECRET
            )
        ) as client:

            response = await client.request(
                method,
                url,
                **kwargs
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                except Exception:
                    error_data = response.text

                logger.error(
                    f"Razorpay API error {response.status_code}: "
                    f"{error_data}"
                )

                raise ValueError(
                    f"Razorpay API error: {error_data}"
                )

            return response.json()

    @staticmethod
    async def create_payment_order(
        user_id: int,
        plan_id: str
    ) -> dict:

        """
        Create a real Razorpay Dynamic UPI QR.
        """

        plan = await db.db.plans.find_one({
            "plan_id": plan_id,
            "status": "active"
        })

        if not plan:
            raise ValueError(
                "Invalid or inactive plan selected."
            )

        price = int(plan["price"])

        if price <= 0:
            raise ValueError(
                "Invalid plan price."
            )

        # Internal payment ID
        payment_id = (
            f"PAY_{uuid.uuid4().hex[:12].upper()}"
        )

        # Razorpay works in paise
        amount_paise = price * 100

        # QR expires after 30 minutes
        close_by = int(
            (
                datetime.now(timezone.utc)
                + timedelta(minutes=30)
            ).timestamp()
        )

        qr_payload = {
            "type": "upi_qr",
            "name": f"Music API - {plan['name']}",
            "usage": "single_use",
            "fixed_amount": True,
            "payment_amount": amount_paise,
            "description": (
                f"Music API {plan['name']} - "
                f"User {user_id}"
            ),
            "close_by": close_by,
            "notes": {
                "payment_id": payment_id,
                "user_id": str(user_id),
                "plan_id": str(plan_id)
            }
        }

        qr = await PaymentService._request(
            "POST",
            "/payments/qr_codes",
            json=qr_payload
        )

        qr_id = qr.get("id")
        image_url = qr.get("image_url")

        if not qr_id or not image_url:
            raise ValueError(
                "Razorpay did not return QR information."
            )

        payment_doc = {
            "payment_id": payment_id,
            "user_id": user_id,
            "plan_id": plan_id,

            "amount": price,
            "amount_paise": amount_paise,
            "currency": "INR",

            "status": "pending",
            "provider": "razorpay",

            "qr_id": qr_id,
            "qr_image_url": image_url,
            "qr_status": qr.get("status"),

            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.fromtimestamp(
                close_by,
                tz=timezone.utc
            ),

            "verified_at": None,
            "transaction_id": None,
            "utr": None
        }

        await db.db.payments.insert_one(
            payment_doc
        )

        logger.info(
            f"Created Razorpay Dynamic QR "
            f"{qr_id} for payment {payment_id}, "
            f"user={user_id}, plan={plan_id}"
        )

        return {
            "payment_id": payment_id,
            "amount": price,
            "currency": "INR",
            "qr_id": qr_id,
            "image_url": image_url,
            "expires_at": payment_doc["expires_at"]
        }

    @staticmethod
    async def get_pending_payment_for_user(
        user_id: int
    ):
        """
        Get latest pending payment that has not expired.
        """

        now = datetime.now(timezone.utc)

        payment = await db.db.payments.find_one(
            {
                "user_id": user_id,
                "status": "pending",
                "expires_at": {
                    "$gt": now
                }
            },
            sort=[
                ("created_at", -1)
            ]
        )

        return payment

    @staticmethod
    async def verify_and_fulfill_payment(
        payment_id: str,
        user_id: int,
        utr: str
    ) -> dict:

        """
        Verify payment directly against Razorpay.

        UTR is NOT trusted by itself.
        We compare it with the payment returned
        by Razorpay for the exact QR.
        """

        payment = await db.db.payments.find_one({
            "payment_id": payment_id,
            "user_id": user_id
        })

        if not payment:
            return {
                "success": False,
                "message": "Payment order not found."
            }

        if payment["status"] == "completed":
            return {
                "success": True,
                "already_completed": True
            }

        if payment["status"] != "pending":
            return {
                "success": False,
                "message": "This payment is no longer pending."
            }

        # Check internal expiry
        expires_at = payment.get("expires_at")

        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(
                    tzinfo=timezone.utc
                )

            if expires_at < datetime.now(timezone.utc):
                await db.db.payments.update_one(
                    {
                        "payment_id": payment_id,
                        "status": "pending"
                    },
                    {
                        "$set": {
                            "status": "expired"
                        }
                    }
                )

                return {
                    "success": False,
                    "message": (
                        "This QR has expired. "
                        "Please create a new payment."
                    )
                }

        utr = utr.strip()

        if not utr:
            return {
                "success": False,
                "message": "Invalid UTR."
            }

        # Razorpay: fetch payments made to this QR
        razorpay_data = await PaymentService._request(
            "GET",
            f"/payments/qr_codes/"
            f"{payment['qr_id']}/payments",
            params={
                "count": 100
            }
        )

        payments = razorpay_data.get(
            "items",
            []
        )

        matched_payment = None

        for rp_payment in payments:

            if rp_payment.get("status") != "captured":
                continue

            # Exact amount check
            if int(rp_payment.get("amount", 0)) != int(
                payment["amount_paise"]
            ):
                continue

            if rp_payment.get("currency") != "INR":
                continue

            acquirer_data = (
                rp_payment.get("acquirer_data")
                or {}
            )

            rrn = str(
                acquirer_data.get("rrn")
                or ""
            ).strip()

            upi_transaction_id = str(
                acquirer_data.get(
                    "upi_transaction_id"
                )
                or ""
            ).strip()

            payment_id_from_razorpay = str(
                rp_payment.get("id")
                or ""
            ).strip()

            # User can submit:
            # UTR/RRN
            # UPI transaction ID
            # Razorpay payment ID
            if utr in {
                rrn,
                upi_transaction_id,
                payment_id_from_razorpay
            }:
                matched_payment = rp_payment
                break

        if not matched_payment:
            logger.warning(
                f"Payment not found for "
                f"payment_id={payment_id}, "
                f"user={user_id}, utr={utr}"
            )

            return {
                "success": False,
                "message": (
                    "Payment not found yet. "
                    "Make sure the payment is successful "
                    "and the UTR is correct."
                )
            }

        razorpay_payment_id = matched_payment["id"]

        # Extra duplicate protection:
        # Do not allow same Razorpay payment to be used twice.
        existing_payment = await db.db.payments.find_one(
            {
                "transaction_id": razorpay_payment_id,
                "status": "completed"
            }
        )

        if existing_payment:
            return {
                "success": False,
                "message": (
                    "This payment has already been used."
                )
            }

        # Atomically mark payment completed
        update_result = await db.db.payments.update_one(
            {
                "payment_id": payment_id,
                "user_id": user_id,
                "status": "pending"
            },
            {
                "$set": {
                    "status": "completed",
                    "verified_at": datetime.now(
                        timezone.utc
                    ),
                    "transaction_id":
                        razorpay_payment_id,
                    "utr": utr,
                    "razorpay_payment":
                        matched_payment
                }
            }
        )

        if update_result.modified_count == 0:
            return {
                "success": False,
                "message": (
                    "Payment was already processed."
                )
            }

        # Activate subscription + API key
        raw_key = await PaymentService._activate_subscription_benefits(
            user_id,
            payment["plan_id"]
        )

        logger.info(
            f"Payment verified successfully: "
            f"{payment_id} / "
            f"Razorpay={razorpay_payment_id}"
        )

        return {
            "success": True,
            "api_key": raw_key,
            "razorpay_payment_id":
                razorpay_payment_id
        }

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
            plan["request_limit"]
        )

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=duration_days)
        )

        now = datetime.now(timezone.utc)

        await db.db.subscriptions.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "plan_id": plan_id,
                    "status": "active",
                    "expires_at": expires_at,
                    "request_limit":
                        request_limit,
                    "updated_at": now
                },
                "$setOnInsert": {
                    "created_at": now
                }
            },
            upsert=True
        )

        raw_key = await APIKeyService.create_api_key(
            user_id=user_id,
            plan_id=plan_id,
            request_limit=request_limit,
            expires_at=expires_at
        )

        logger.info(
            f"Activated subscription and generated "
            f"API key for user {user_id}, "
            f"plan={plan_id}"
        )

        return raw_key
