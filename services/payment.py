import uuid
from datetime import datetime, timezone, timedelta

import httpx

from database import db
from services.api_keys import APIKeyService
from config import settings
from utils.logger import logger


RAZORPAY_API_URL = "https://api.razorpay.com/v1"


class PaymentService:

    # ==========================================
    # CONFIG CHECK
    # ==========================================

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

    # ==========================================
    # RAZORPAY REQUEST
    # ==========================================

    @staticmethod
    async def _request(
        method: str,
        endpoint: str,
        **kwargs
    ):

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
                    f"Razorpay API error | "
                    f"status={response.status_code} | "
                    f"endpoint={endpoint} | "
                    f"response={error_data}"
                )

                raise ValueError(
                    f"Razorpay API error "
                    f"{response.status_code}: "
                    f"{error_data}"
                )

            try:
                return response.json()
            except Exception as e:

                logger.error(
                    f"Invalid Razorpay JSON response: {e}"
                )

                raise ValueError(
                    "Invalid response received from Razorpay."
                )

    # ==========================================
    # CREATE UPI PAYMENT LINK
    # ==========================================

    @staticmethod
    async def create_payment_order(
        user_id: int,
        plan_id: str
    ) -> dict:

        """
        Create a Razorpay UPI Payment Link.

        User can open the link and pay using
        supported UPI/payment options.
        """

        # --------------------------------------
        # Get plan
        # --------------------------------------

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

        # --------------------------------------
        # Internal payment ID
        # --------------------------------------

        payment_id = (
            f"PAY_{uuid.uuid4().hex[:12].upper()}"
        )

        # --------------------------------------
        # Amount in paise
        # --------------------------------------

        amount_paise = price * 100

        # --------------------------------------
        # Payment Link expiry
        # 30 minutes
        # --------------------------------------

        expire_by = int(
            (
                datetime.now(timezone.utc)
                + timedelta(minutes=30)
            ).timestamp()
        )

        # Razorpay reference_id max length is 40
        reference_id = payment_id[:40]

        # --------------------------------------
        # Razorpay UPI Payment Link payload
        # --------------------------------------

        payload = {
            "upi_link": True,
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "expire_by": expire_by,
            "reference_id": reference_id,
            "description": (
                f"Music API - {plan['name']}"
            ),
            "notes": {
                "payment_id": payment_id,
                "user_id": str(user_id),
                "plan_id": str(plan_id)
            }
        }

        logger.info(
            f"Creating Razorpay UPI Payment Link | "
            f"user={user_id} | "
            f"plan={plan_id} | "
            f"amount={price}"
        )

        # --------------------------------------
        # Create Payment Link
        # --------------------------------------

        link = await PaymentService._request(
            "POST",
            "/payment_links",
            json=payload
        )

        razorpay_link_id = link.get("id")
        short_url = link.get("short_url")

        if not razorpay_link_id:
            raise ValueError(
                "Razorpay did not return Payment Link ID."
            )

        if not short_url:
            raise ValueError(
                "Razorpay did not return Payment Link URL."
            )

        # --------------------------------------
        # Save payment in MongoDB
        # --------------------------------------

        payment_doc = {
            "payment_id": payment_id,

            "user_id": user_id,

            "plan_id": plan_id,

            "amount": price,

            "amount_paise": amount_paise,

            "currency": "INR",

            "status": "pending",

            "provider": "razorpay",

            "payment_link_id": razorpay_link_id,

            "payment_link_url": short_url,

            "reference_id": reference_id,

            "created_at": datetime.now(
                timezone.utc
            ),

            "expires_at": datetime.fromtimestamp(
                expire_by,
                tz=timezone.utc
            ),

            "verified_at": None,

            "transaction_id": None,

            "utr": None,

            "razorpay_payment_link": link
        }

        await db.db.payments.insert_one(
            payment_doc
        )

        logger.info(
            f"Razorpay Payment Link created | "
            f"link={razorpay_link_id} | "
            f"payment={payment_id} | "
            f"user={user_id}"
        )

        return {
            "payment_id": payment_id,
            "amount": price,
            "currency": "INR",
            "payment_link_id": razorpay_link_id,
            "payment_url": short_url,
            "expires_at": payment_doc["expires_at"]
        }

    # ==========================================
    # GET PENDING PAYMENT
    # ==========================================

    @staticmethod
    async def get_pending_payment_for_user(
        user_id: int
    ):

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

    # ==========================================
    # VERIFY PAYMENT
    # ==========================================

    @staticmethod
    async def verify_and_fulfill_payment(
        payment_id: str,
        user_id: int,
        utr: str = None
    ) -> dict:

        """
        Verify Razorpay Payment Link directly.

        UTR is NOT required.

        Razorpay Payment Link is fetched from API
        and its payment status is checked.
        """

        # --------------------------------------
        # Get local payment
        # --------------------------------------

        payment = await db.db.payments.find_one({
            "payment_id": payment_id,
            "user_id": user_id
        })

        if not payment:

            return {
                "success": False,
                "message": "Payment order not found."
            }

        # --------------------------------------
        # Already completed
        # --------------------------------------

        if payment["status"] == "completed":

            return {
                "success": True,
                "already_completed": True
            }

        # --------------------------------------
        # Check pending status
        # --------------------------------------

        if payment["status"] != "pending":

            return {
                "success": False,
                "message": (
                    "This payment is no longer pending."
                )
            }

        # --------------------------------------
        # Local expiry
        # --------------------------------------

        expires_at = payment.get(
            "expires_at"
        )

        if expires_at:

            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(
                    tzinfo=timezone.utc
                )

            if expires_at < datetime.now(
                timezone.utc
            ):

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
                        "This payment link has expired. "
                        "Please create a new payment."
                    )
                }

        # --------------------------------------
        # Razorpay Payment Link ID
        # --------------------------------------

        razorpay_link_id = payment.get(
            "payment_link_id"
        )

        if not razorpay_link_id:

            return {
                "success": False,
                "message": (
                    "Payment Link ID not found."
                )
            }

        # --------------------------------------
        # Fetch Payment Link from Razorpay
        # --------------------------------------

        try:

            razorpay_link = (
                await PaymentService._request(
                    "GET",
                    f"/payment_links/"
                    f"{razorpay_link_id}"
                )
            )

        except Exception as e:

            logger.error(
                f"Payment verification failed: {e}"
            )

            return {
                "success": False,
                "message": (
                    "Unable to contact Razorpay. "
                    "Please try again."
                )
            }

        # --------------------------------------
        # Payment Link status
        # --------------------------------------

        link_status = (
            razorpay_link.get("status")
            or ""
        ).lower()

        amount_paid = int(
            razorpay_link.get(
                "amount_paid",
                0
            )
            or 0
        )

        required_amount = int(
            payment["amount_paise"]
        )

        # --------------------------------------
        # Not paid yet
        # --------------------------------------

        if link_status != "paid":

            if link_status in {
                "expired",
                "cancelled"
            }:

                await db.db.payments.update_one(
                    {
                        "payment_id": payment_id,
                        "status": "pending"
                    },
                    {
                        "$set": {
                            "status": link_status
                        }
                    }
                )

                return {
                    "success": False,
                    "message": (
                        f"Payment link is "
                        f"{link_status}."
                    )
                }

            return {
                "success": False,
                "message": (
                    "Payment has not been received yet. "
                    "Please complete the payment first."
                )
            }

        # --------------------------------------
        # Exact amount verification
        # --------------------------------------

        if amount_paid != required_amount:

            logger.error(
                f"Amount mismatch | "
                f"payment={payment_id} | "
                f"required={required_amount} | "
                f"paid={amount_paid}"
            )

            return {
                "success": False,
                "message": (
                    "Payment amount mismatch."
                )
            }

        # --------------------------------------
        # Get captured payment
        # --------------------------------------

        razorpay_payments = (
            razorpay_link.get("payments")
            or []
        )

        matched_payment = None

        for rp_payment in razorpay_payments:

            if not isinstance(
                rp_payment,
                dict
            ):
                continue

            payment_status = str(
                rp_payment.get("status")
                or ""
            ).lower()

            if payment_status != "captured":
                continue

            rp_amount = int(
                rp_payment.get(
                    "amount",
                    0
                )
                or 0
            )

            if rp_amount != required_amount:
                continue

            if (
                rp_payment.get("currency")
                != "INR"
            ):
                continue

            matched_payment = rp_payment

            break

        # --------------------------------------
        # If payment details are unavailable
        # --------------------------------------

        if not matched_payment:

            return {
                "success": False,
                "message": (
                    "Payment is marked paid, "
                    "but captured payment details "
                    "are not available yet. "
                    "Please try Verify again."
                )
            }

        razorpay_payment_id = str(
            matched_payment.get("id")
            or ""
        ).strip()

        if not razorpay_payment_id:

            return {
                "success": False,
                "message": (
                    "Razorpay payment ID not found."
                )
            }

        # --------------------------------------
        # Duplicate payment protection
        # --------------------------------------

        existing_payment = (
            await db.db.payments.find_one(
                {
                    "transaction_id":
                        razorpay_payment_id,
                    "status": "completed"
                }
            )
        )

        if existing_payment:

            # Same user's same payment already done
            if (
                existing_payment.get("user_id")
                == user_id
            ):

                return {
                    "success": True,
                    "already_completed": True
                }

            return {
                "success": False,
                "message": (
                    "This payment has already "
                    "been used."
                )
            }

        # --------------------------------------
        # Atomically complete local payment
        # --------------------------------------

        update_result = (
            await db.db.payments.update_one(
                {
                    "payment_id": payment_id,
                    "user_id": user_id,
                    "status": "pending"
                },
                {
                    "$set": {
                        "status": "completed",

                        "verified_at":
                            datetime.now(
                                timezone.utc
                            ),

                        "transaction_id":
                            razorpay_payment_id,

                        "utr": None,

                        "razorpay_payment":
                            matched_payment,

                        "razorpay_link_status":
                            link_status,

                        "amount_paid":
                            amount_paid
                    }
                }
            )
        )

        if update_result.modified_count == 0:

            return {
                "success": False,
                "message": (
                    "Payment was already processed."
                )
            }

        # --------------------------------------
        # Activate subscription + API key
        # --------------------------------------

        try:

            raw_key = (
                await PaymentService
                ._activate_subscription_benefits(
                    user_id,
                    payment["plan_id"]
                )
            )

        except Exception as e:

            logger.error(
                f"Subscription activation failed "
                f"after payment {payment_id}: {e}",
                exc_info=True
            )

            return {
                "success": False,
                "message": (
                    "Payment received, but subscription "
                    "activation failed. Please contact support."
                )
            }

        logger.info(
            f"Payment verified successfully | "
            f"payment={payment_id} | "
            f"razorpay={razorpay_payment_id} | "
            f"user={user_id}"
        )

        return {
            "success": True,
            "api_key": raw_key,
            "razorpay_payment_id":
                razorpay_payment_id
        }

    # ==========================================
    # ACTIVATE SUBSCRIPTION
    # ==========================================

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
            plan.get(
                "request_limit",
                0
            )
        )

        if request_limit <= 0:

            raise ValueError(
                f"Invalid request_limit "
                f"for plan {plan_id}."
            )

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=duration_days)
        )

        now = datetime.now(timezone.utc)

        # --------------------------------------
        # Subscription
        # --------------------------------------

        await db.db.subscriptions.update_one(
            {
                "user_id": user_id
            },
            {
                "$set": {
                    "plan_id": plan_id,
                    "status": "active",
                    "expires_at": expires_at,
                    "request_limit": request_limit,
                    "updated_at": now
                },
                "$setOnInsert": {
                    "created_at": now
                }
            },
            upsert=True
        )

        # --------------------------------------
        # Generate API key
        # --------------------------------------

        raw_key = (
            await APIKeyService.create_api_key(
                user_id=user_id,
                plan_id=plan_id,
                request_limit=request_limit,
                expires_at=expires_at
            )
        )

        logger.info(
            f"Subscription activated | "
            f"user={user_id} | "
            f"plan={plan_id} | "
            f"expires={expires_at}"
        )

        return raw_key
