from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import connect_to_mongo, close_mongo_connection, db
from middleware.auth import verify_api_request
from services.downloader import DownloadService
from utils.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Starting REST API Server...")
    await connect_to_mongo()
    yield
    # Shutdown tasks
    logger.info("Shutting down REST API Server...")
    await close_mongo_connection()

app = FastAPI(
    title="Music Bot API Service",
    version="1.0.0",
    docs_url=None, # Custom docs handled below
    redoc_url=None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/download")
async def download_media(
    request: Request,
    url: str = Query(..., description="YouTube Video ID or direct URL"),
    type: str = Query(..., regex="^(audio|video)$", description="Type of download: audio or video"),
    api_key: str = Query(..., description="User API Key")
):
    """Compatible download endpoint for the existing Music Bot."""
    # Validate API key via middleware dependency logic
    key_doc = await verify_api_request(request)
    
    # Execute download extraction via service
    download_result = await DownloadService.process_download(url, type)
    
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "Download completed",
            "data": {
                "url": download_result["url"],
                "type": download_result["type"],
                "title": download_result.get("title"),
                "duration": download_result.get("duration")
            }
        }
    )

@app.get("/docs")
async def api_documentation():
    """Custom API Documentation endpoint."""
    return {
        "title": "Music Bot API Documentation",
        "base_url": settings.API_BASE_URL,
        "authentication": {
            "type": "Query Parameter",
            "parameter_name": "api_key",
            "description": "Pass your secure API key (starting with MSP_) as a query parameter."
        },
        "endpoints": {
            "/download": {
                "method": "GET",
                "description": "Downloads or extracts media from a YouTube ID or URL.",
                "parameters": {
                    "url": "String (Required) - YouTube Video ID or full link",
                    "type": "String (Required) - Options: 'audio' or 'video'",
                    "api_key": "String (Required) - Your active API key"
                },
                "examples": {
                    "audio": f"{settings.API_BASE_URL}/download?url=dQw4w9WgXcQ&type=audio&api_key=MSP_YOUR_KEY",
                    "video": f"{settings.API_BASE_URL}/download?url=dQw4w9WgXcQ&type=video&api_key=MSP_YOUR_KEY"
                }
            }
        },
        "error_responses": {
            "401": {"success": False, "error": "MISSING_API_KEY or INVALID_API_KEY"},
            "403": {"success": False, "error": "SUBSCRIPTION_EXPIRED"},
            "429": {"success": False, "error": "REQUEST_LIMIT_EXCEEDED"},
            "400": {"success": False, "error": "INVALID_PARAMETERS"},
            "500": {"success": False, "error": "DOWNLOAD_SERVICE_ERROR"}
        }
    }
