from fastapi import Request, HTTPException
from services.api_keys import APIKeyService
from database import db
from datetime import datetime, timezone

async def verify_api_request(request: Request) -> dict:
    """FastAPI Dependency to validate incoming API requests and increment usage."""
    api_key = request.query_params.get("api_key")
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={"success": False, "error": "MISSING_API_KEY"}
        )

    validation_result = await APIKeyService.validate_api_key(api_key)
    
    if not validation_result["valid"]:
        error_code = validation_result["error_code"]
        status_code = validation_result["status_code"]
        
        error_mapping = {
            "INVALID_API_KEY": "INVALID_API_KEY",
            "KEY_REVOKED_OR_INACTIVE": "INVALID_API_KEY",
            "SUBSCRIPTION_EXPIRED": "SUBSCRIPTION_EXPIRED",
            "REQUEST_LIMIT_EXCEEDED": "REQUEST_LIMIT_EXCEEDED"
        }
        
        raise HTTPException(
            status_code=status_code,
            detail={"success": False, "error": error_mapping.get(error_code, "UNAUTHORIZED")}
        )

    key_doc = validation_result["key_doc"]
    
    # Increment usage and update last used timestamp atomically
    await db.db.api_keys.update_one(
        {"_id": key_doc["_id"]},
        {
            "$inc": {"requests_used": 1},
            "$set": {"last_used_at": datetime.now(timezone.utc)}
        }
    )

    # Log usage record
    await db.db.api_usage.insert_one({
        "user_id": key_doc["user_id"],
        "api_key_hash": key_doc["api_key_hash"],
        "timestamp": datetime.now(timezone.utc),
        "endpoint": request.url.path
    })

    return key_doc
