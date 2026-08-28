import os
import asyncio
import yt_dlp
from fastapi import HTTPException
from config import settings
from utils.logger import logger

class DownloadService:
    # Semaphore to limit concurrent downloads and prevent resource exhaustion
    semaphore = asyncio.Semaphore(3)

    @staticmethod
    def ensure_download_dir():
        if not os.path.exists(settings.DOWNLOAD_DIR):
            os.makedirs(settings.DOWNLOAD_DIR, exist_ok=True)

    @classmethod
    async def process_download(cls, url: str, download_type: str) -> dict:
        cls.ensure_download_dir()
        
        # Format video identifier / URL
        if not url.startswith("http"):
            target_url = f"https://www.youtube.com/watch?v={url}"
        else:
            target_url = url

        async with cls.semaphore:
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(
                    None, 
                    cls._extract_and_download, 
                    target_url, 
                    download_type
                )
                return result
            except Exception as e:
                logger.error(f"Download execution error for {target_url}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail={"success": False, "error": "DOWNLOAD_SERVICE_ERROR", "message": str(e)}
                )

    @staticmethod
    def _extract_and_download(target_url: str, download_type: str) -> dict:
        output_template = os.path.join(settings.DOWNLOAD_DIR, "%(id)s.%(ext)s")
        
        if download_type == "audio":
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
            }
        elif download_type == "video":
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
            }
        else:
            raise ValueError("Invalid download type. Must be 'audio' or 'video'.")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(target_url, download=True)
                file_id = info.get("id")
                ext = "mp3" if download_type == "audio" else "mp4"
                file_path = os.path.join(settings.DOWNLOAD_DIR, f"{file_id}.{ext}")
                
                # In a complete architecture, you can either stream this file, 
                # upload it to a CDN/storage, or return the local file path/accessible URL.
                # Here we return the metadata package matching your required JSON interface.
                return {
                    "url": target_url,
                    "type": download_type,
                    "file_id": file_id,
                    "title": info.get("title"),
                    "duration": info.get("duration"),
                    "file_path": file_path
                }
            except Exception as e:
                raise RuntimeError(f"yt-dlp failed: {str(e)}")
