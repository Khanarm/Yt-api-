import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    API_ID: int
    API_HASH: str
    BOT_TOKEN: str
    MONGO_DB_URI: str
    OWNER_ID: int

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_BASE_URL: str

    PAYMENT_PROVIDER: str = "dummy"
    PAYMENT_API_KEY: Optional[str] = None
    PAYMENT_SECRET: Optional[str] = None

    SUPPORT_CHANNEL: str = "@support"
    SUPPORT_GROUP: str = "@support_group"

    DOWNLOAD_DIR: str = "downloads"
    RATE_LIMIT: str = "60/minute"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
