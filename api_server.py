from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask

from config import settings
from database import connect_to_mongo, close_mongo_connection
from middleware.auth import verify_api_request
from services.downloader import DownloadService
from utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting REST API Server...")

    await connect_to_mongo()

    yield

    logger.info("Shutting down REST API Server...")

    await close_mongo_connection()


app = FastAPI(
    title="Music Bot API",
    version="2.0.0",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def home():
    return {
        "success": True,
        "name": "Music Bot API",
        "version": "2.0.0",
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    return {
        "success": True,
        "status": "ok",
    }


@app.get("/download")
async def download_media(
    request: Request,
    url: str = Query(
        ...,
        description="YouTube video ID or supported URL",
    ),
    type: str = Query(
        ...,
        pattern="^(audio|video)$",
        description="audio or video",
    ),
    api_key: str = Query(
        ...,
        description="Your API key",
    ),
    key_doc: dict = Depends(verify_api_request),
):
    """
    Download endpoint compatible with the Telegram Music Bot.

    The important difference from the old version:
    This endpoint returns the actual media file instead of JSON.
    """

    try:
        result = await DownloadService.process_download(
            url=url,
            download_type=type,
        )

        file_path = result["file_path"]
        media_type = result["media_type"]
        filename = result["filename"]

        logger.info(
            f"Sending file: {filename} | "
            f"user={key_doc.get('user_id')}"
        )

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
            background=BackgroundTask(
                DownloadService.cleanup_file,
                file_path,
            ),
        )

    except Exception as e:
        logger.error(f"Download endpoint error: {e}")

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "DOWNLOAD_SERVICE_ERROR",
                "message": str(e),
            },
        )


@app.get("/info")
async def api_info():
    return {
        "success": True,
        "name": "Music Bot API",
        "version": "2.0.0",
        "endpoints": {
            "health": "/health",
            "download": "/download",
            "docs": "/docs",
        },
    }


@app.get("/docs")
async def api_documentation():
    base_url = getattr(
        settings,
        "API_BASE_URL",
        "",
    ).rstrip("/")

    return {
        "success": True,
        "title": "Music Bot API Documentation",
        "version": "2.0.0",
        "base_url": base_url,

        "authentication": {
            "type": "query",
            "parameter": "api_key",
            "example": "MSP_YOUR_API_KEY",
        },

        "endpoints": {
            "/download": {
                "method": "GET",
                "description": (
                    "Downloads permitted media and returns "
                    "the actual media file."
                ),

                "parameters": {
                    "url": "Required - video ID or supported URL",
                    "type": "Required - audio or video",
                    "api_key": "Required - active API key",
                },

                "example": {
                    "audio": (
                        f"{base_url}/download"
                        "?url=VIDEO_ID"
                        "&type=audio"
                        "&api_key=MSP_YOUR_KEY"
                    ),
                    "video": (
                        f"{base_url}/download"
                        "?url=VIDEO_ID"
                        "&type=video"
                        "&api_key=MSP_YOUR_KEY"
                    ),
                },

                "response": (
                    "Binary audio/video file"
                ),
            }
        },

        "errors": {
            "400": "INVALID_PARAMETERS",
            "401": "MISSING_API_KEY / INVALID_API_KEY",
            "403": "SUBSCRIPTION_EXPIRED",
            "429": "REQUEST_LIMIT_EXCEEDED",
            "500": "DOWNLOAD_SERVICE_ERROR",
        },
    }
