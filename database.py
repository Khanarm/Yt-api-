from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import settings
from utils.logger import logger

class Database:
    client: AsyncIOMotorClient = None
    db: AsyncIOMotorDatabase = None

db = Database()

async def connect_to_mongo():
    try:
        db.client = AsyncIOMotorClient(settings.MONGO_DB_URI)
        db.db = db.client.get_default_database()
        
        # Ping check
        await db.client.admin.command('ping')
        logger.info("Successfully connected to MongoDB.")
        
        await create_indexes()
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise e

async def close_mongo_connection():
    if db.client:
        db.client.close()
        logger.info("MongoDB connection closed.")

async def create_indexes():
    try:
        # Users Collection
        await db.db.users.create_index("user_id", unique=True)
        
        # Subscriptions Collection
        await db.db.subscriptions.create_index("user_id")
        await db.db.subscriptions.create_index("status")
        
        # Plans Collection
        await db.db.plans.create_index("plan_id", unique=True)
        
        # API Keys Collection
        await db.db.api_keys.create_index("user_id")
        await db.db.api_keys.create_index("api_key_hash", unique=True)
        await db.db.api_keys.create_index("key_prefix")
        
        # Payments Collection
        await db.db.payments.create_index("payment_id", unique=True)
        await db.db.payments.create_index("user_id")
        
        # API Usage Collection
        await db.db.api_usage.create_index([("user_id", 1), ("timestamp", -1)])
        
        logger.info("Database indexes successfully verified/created.")
    except Exception as e:
        logger.error(f"Error creating database indexes: {e}")
        raise e
