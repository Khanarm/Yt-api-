import secrets
import hashlib
from datetime import datetime, timezone
from database import db
from utils.logger import logger

class APIKeyService:
    @staticmethod
    def generate_raw_key() -> tuple[str, str, str]:
        """Generates a secure API key, its prefix, and its SHA-256 hash."""
        random_token = secrets.token_urlsafe(32)
        raw_key = f"MSP_{random_token}"
        key_prefix = raw_key[:8]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key, key_prefix, key_hash

    @staticmethod
    async def create_api_key(user_id: int, plan_id: str, request_limit: int, expires_at: datetime) -> str:
        """Revokes any existing active keys for the user and creates a new secure API key."""
        # Deactivate old keys
        await db.db.api_keys.update_many(
            {"user_id": user_id, "status": "active"},
            {"$set": {"status": "revoked"}}
        )

        raw_key, key_prefix, key_hash = APIKeyService.generate_raw_key()
        
        key_doc = {
            "user_id": user_id,
            "api_key_hash": key_hash,
            "key_prefix": key_prefix,
            "plan_id": plan_id,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "request_limit": request_limit,
            "requests_used": 0,
            "last_used_at": None
        }

        await db.db.api_keys.insert_one(key_doc)
        logger.info(f"Generated new API key for user {user_id} with plan {plan_id}.")
        return raw_key

    @staticmethod
    async def get_active_key_info(user_id: int) -> dict | None:
        return await db.db.api_keys.find_one({"user_id": user_id, "status": "active"})

    @staticmethod
    async def revoke_user_keys(user_id: int) -> bool:
        result = await db.db.api_keys.update_many(
            {"user_id": user_id, "status": "active"},
            {"$set": {"status": "revoked"}}
        )
        return result.modified_count > 0

    @staticmethod
    async def validate_api_key(raw_key: str) -> dict:
        """Validates the raw API key against the database, checking expiry and limits."""
        if not raw_key or not raw_key.startswith("MSP_"):
            return {"valid": False, "error_code": "INVALID_API_KEY", "status_code": 401}

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_doc = await db.db.api_keys.find_one({"api_key_hash": key_hash})

        if not key_doc:
            return {"valid": False, "error_code": "INVALID_API_KEY", "status_code": 401}

        if key_doc["status"] != "active":
            return {"valid": False, "error_code": "KEY_REVOKED_OR_INACTIVE", "status_code": 401}

        now = datetime.now(timezone.utc)
        expires_at = key_doc["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            await db.db.api_keys.update_one({"_id": key_doc["_id"]}, {"$set": {"status": "expired"}})
            await db.db.subscriptions.update_many({"user_id": key_doc["user_id"]}, {"$set": {"status": "expired"}})
            return {"valid": False, "error_code": "SUBSCRIPTION_EXPIRED", "status_code": 403}

        if key_doc["requests_used"] >= key_doc["request_limit"]:
            return {"valid": False, "error_code": "REQUEST_LIMIT_EXCEEDED", "status_code": 429}

        return {"valid": True, "key_doc": key_doc}
