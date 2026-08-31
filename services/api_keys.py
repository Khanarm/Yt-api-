import secrets
import hashlib
import base64

from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken

from database import db
from config import settings
from utils.logger import logger


class APIKeyService:

    # ======================================================
    # ENCRYPTION
    # ======================================================

    @staticmethod
    def _get_fernet() -> Fernet:

        secret = (
            settings.API_KEY_ENCRYPTION_SECRET
            or settings.BOT_TOKEN
        )

        digest = hashlib.sha256(
            secret.encode()
        ).digest()

        fernet_key = base64.urlsafe_b64encode(
            digest
        )

        return Fernet(fernet_key)

    # ======================================================
    # ENCRYPT API KEY
    # ======================================================

    @staticmethod
    def encrypt_raw_key(
        raw_key: str
    ) -> str:

        return (
            APIKeyService
            ._get_fernet()
            .encrypt(
                raw_key.encode()
            )
            .decode()
        )

    # ======================================================
    # DECRYPT API KEY
    # ======================================================

    @staticmethod
    def decrypt_raw_key(
        encrypted_key: str
    ) -> str | None:

        try:

            return (
                APIKeyService
                ._get_fernet()
                .decrypt(
                    encrypted_key.encode()
                )
                .decode()
            )

        except (
            InvalidToken,
            ValueError,
            TypeError,
        ):

            return None

    # ======================================================
    # GENERATE RAW API KEY
    # ======================================================

    @staticmethod
    def generate_raw_key():

        random_token = (
            secrets.token_urlsafe(32)
        )

        raw_key = (
            f"MSP_{random_token}"
        )

        key_prefix = (
            raw_key[:8]
        )

        key_hash = hashlib.sha256(
            raw_key.encode()
        ).hexdigest()

        return (
            raw_key,
            key_prefix,
            key_hash,
        )

    # ======================================================
    # CREATE API KEY
    # ======================================================

    @staticmethod
    async def create_api_key(
        user_id: int,
        plan_id: str,
        request_limit: int,
        expires_at: datetime,
    ) -> str:

        # --------------------------------------------------
        # IMPORTANT
        # A new key is created ONLY when a new plan is
        # successfully purchased.
        #
        # My API Key screen NEVER calls this function.
        # --------------------------------------------------

        await db.db.api_keys.update_many(
            {
                "user_id": user_id,
                "status": "active",
            },
            {
                "$set": {
                    "status": "revoked",
                }
            },
        )

        # Generate new key
        raw_key, key_prefix, key_hash = (
            APIKeyService.generate_raw_key()
        )

        # Store encrypted copy so owner can see it
        # from Telegram bot.
        encrypted_key = (
            APIKeyService.encrypt_raw_key(
                raw_key
            )
        )

        key_doc = {

            "user_id": user_id,

            # Used for API authentication
            "api_key_hash": key_hash,

            # Used ONLY to display the key
            # to the owner.
            "api_key_encrypted": encrypted_key,

            "key_prefix": key_prefix,

            "plan_id": plan_id,

            "status": "active",

            "created_at": datetime.now(
                timezone.utc
            ),

            "expires_at": expires_at,

            # -1 = unlimited
            "request_limit": int(
                request_limit
            ),

            "requests_used": 0,

            "last_used_at": None,
        }

        await db.db.api_keys.insert_one(
            key_doc
        )

        logger.info(
            "Generated API key | user=%s plan=%s",
            user_id,
            plan_id,
        )

        return raw_key

    # ======================================================
    # GET ACTIVE KEY
    # ======================================================

    @staticmethod
    async def get_active_key_info(
        user_id: int
    ) -> dict | None:

        return await db.db.api_keys.find_one(
            {
                "user_id": user_id,
                "status": "active",
            }
        )

    # ======================================================
    # GET KEY FOR DISPLAY
    # ======================================================

    @staticmethod
    def get_display_key(
        key_doc: dict
    ) -> str | None:

        encrypted_key = (
            key_doc.get(
                "api_key_encrypted"
            )
        )

        if encrypted_key:

            return (
                APIKeyService
                .decrypt_raw_key(
                    encrypted_key
                )
            )

        # Old database format
        # If old key was stored directly,
        # support it.
        old_key = key_doc.get(
            "api_key"
        )

        if old_key:
            return old_key

        # SHA-256 hash cannot be reversed.
        return None

    # ======================================================
    # REVOKE USER KEYS
    # ======================================================

    @staticmethod
    async def revoke_user_keys(
        user_id: int
    ) -> bool:

        result = await db.db.api_keys.update_many(
            {
                "user_id": user_id,
                "status": "active",
            },
            {
                "$set": {
                    "status": "revoked",
                }
            },
        )

        return (
            result.modified_count > 0
        )

    # ======================================================
    # VALIDATE API KEY
    # ======================================================

    @staticmethod
    async def validate_api_key(
        raw_key: str
    ) -> dict:

        # Basic format check
        if (
            not raw_key
            or not raw_key.startswith("MSP_")
        ):

            return {
                "valid": False,
                "error_code": "INVALID_API_KEY",
                "status_code": 401,
            }

        # Hash supplied key
        key_hash = hashlib.sha256(
            raw_key.encode()
        ).hexdigest()

        # Find key
        key_doc = await db.db.api_keys.find_one(
            {
                "api_key_hash": key_hash
            }
        )

        if not key_doc:

            return {
                "valid": False,
                "error_code": "INVALID_API_KEY",
                "status_code": 401,
            }

        # Check status
        if key_doc.get("status") != "active":

            return {
                "valid": False,
                "error_code": "KEY_REVOKED_OR_INACTIVE",
                "status_code": 401,
            }

        # ==================================================
        # EXPIRY
        # ==================================================

        now = datetime.now(
            timezone.utc
        )

        expires_at = key_doc.get(
            "expires_at"
        )

        if not expires_at:

            return {
                "valid": False,
                "error_code": "SUBSCRIPTION_EXPIRED",
                "status_code": 403,
            }

        if expires_at.tzinfo is None:

            expires_at = (
                expires_at.replace(
                    tzinfo=timezone.utc
                )
            )

        if expires_at < now:

            await db.db.api_keys.update_one(
                {
                    "_id": key_doc["_id"]
                },
                {
                    "$set": {
                        "status": "expired"
                    }
                },
            )

            await db.db.subscriptions.update_many(
                {
                    "user_id": key_doc["user_id"]
                },
                {
                    "$set": {
                        "status": "expired"
                    }
                },
            )

            return {
                "valid": False,
                "error_code": "SUBSCRIPTION_EXPIRED",
                "status_code": 403,
            }

        # ==================================================
        # REQUEST LIMIT
        # ==================================================

        request_limit = int(
            key_doc.get(
                "request_limit",
                0
            )
        )

        requests_used = int(
            key_doc.get(
                "requests_used",
                0
            )
        )

        # -1 = unlimited
        if (
            request_limit != -1
            and requests_used >= request_limit
        ):

            return {
                "valid": False,
                "error_code": "REQUEST_LIMIT_EXCEEDED",
                "status_code": 429,
            }

        return {
            "valid": True,
            "key_doc": key_doc,
        }
