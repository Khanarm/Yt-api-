import os
import asyncio
import glob

import yt_dlp
from fastapi import HTTPException

from config import settings
from utils.logger import logger


class DownloadService:

    # Maximum simultaneous downloads
    semaphore = asyncio.Semaphore(3)

    @staticmethod
    def ensure_download_dir():
        os.makedirs(
            settings.DOWNLOAD_DIR,
            exist_ok=True,
        )

    @staticmethod
    def cleanup_file(file_path: str):
        """
        Delete downloaded file after FastAPI
        has finished sending it to the client.
        """

        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)

                logger.info(
                    f"Temporary file deleted: {file_path}"
                )

        except Exception as e:
            logger.warning(
                f"Could not delete file {file_path}: {e}"
            )

    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Convert a video ID into a YouTube URL.

        Full URLs are kept unchanged.
        """

        url = url.strip()

        if not url:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "INVALID_URL",
                },
            )

        if not url.startswith(("http://", "https://")):
            return (
                "https://www.youtube.com/watch?v="
                + url
            )

        return url

    @classmethod
    async def process_download(
        cls,
        url: str,
        download_type: str,
    ) -> dict:

        cls.ensure_download_dir()

        if download_type not in ("audio", "video"):
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "INVALID_TYPE",
                    "message": (
                        "type must be audio or video"
                    ),
                },
            )

        target_url = cls.normalize_url(url)

        async with cls.semaphore:

            loop = asyncio.get_running_loop()

            try:
                result = await loop.run_in_executor(
                    None,
                    cls._extract_and_download,
                    target_url,
                    download_type,
                )

                if not result.get("file_path"):
                    raise RuntimeError(
                        "Download completed but "
                        "file path was not found."
                    )

                if not os.path.isfile(
                    result["file_path"]
                ):
                    raise RuntimeError(
                        "Downloaded file does not exist."
                    )

                return result

            except HTTPException:
                raise

            except Exception as e:

                logger.error(
                    f"Download failed: {target_url} | {e}"
                )

                raise HTTPException(
                    status_code=500,
                    detail={
                        "success": False,
                        "error": "DOWNLOAD_SERVICE_ERROR",
                        "message": str(e),
                    },
                )

    @staticmethod
    def _extract_and_download(
        target_url: str,
        download_type: str,
    ) -> dict:

        download_dir = settings.DOWNLOAD_DIR

        # Unique temporary filename.
        output_template = os.path.join(
            download_dir,
            "%(id)s.%(ext)s",
        )

        if download_type == "audio":

            ydl_opts = {
                "format": (
                    "bestaudio/best"
                ),

                "outtmpl": output_template,

                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],

                "quiet": True,
                "no_warnings": True,

                # Do not keep extra downloaded fragments.
                "keepvideo": False,

                "noplaylist": True,
            }

        else:

            ydl_opts = {
                "format": (
                    "bestvideo[ext=mp4]+"
                    "bestaudio[ext=m4a]/"
                    "best[ext=mp4]/best"
                ),

                "outtmpl": output_template,

                "merge_output_format": "mp4",

                "quiet": True,
                "no_warnings": True,

                "noplaylist": True,
            }

        try:

            with yt_dlp.YoutubeDL(
                ydl_opts
            ) as ydl:

                info = ydl.extract_info(
                    target_url,
                    download=True,
                )

                if not info:
                    raise RuntimeError(
                        "No media information returned."
                    )

                video_id = info.get("id")

                if not video_id:
                    raise RuntimeError(
                        "Could not determine video ID."
                    )

                title = info.get(
                    "title",
                    video_id,
                )

                duration = info.get(
                    "duration"
                )

                # ------------------------------------------------
                # Find the actual downloaded file.
                # This is more reliable than assuming only
                # <id>.mp3 or <id>.mp4 exists.
                # ------------------------------------------------

                possible_files = []

                if download_type == "audio":

                    possible_files = [
                        os.path.join(
                            download_dir,
                            f"{video_id}.mp3",
                        )
                    ]

                else:

                    possible_files = [
                        os.path.join(
                            download_dir,
                            f"{video_id}.mp4",
                        )
                    ]

                # If exact path wasn't found, search by ID.
                existing_file = None

                for file_path in possible_files:

                    if os.path.isfile(file_path):
                        existing_file = file_path
                        break

                if existing_file is None:

                    matches = glob.glob(
                        os.path.join(
                            download_dir,
                            f"{video_id}.*",
                        )
                    )

                    # Ignore temporary files.
                    matches = [
                        x
                        for x in matches
                        if os.path.isfile(x)
                        and not x.endswith(
                            (".part", ".ytdl")
                        )
                    ]

                    if matches:
                        existing_file = max(
                            matches,
                            key=os.path.getmtime,
                        )

                if existing_file is None:
                    raise RuntimeError(
                        "Downloaded file could not be found."
                    )

                # ------------------------------------------------
                # Final filename
                # ------------------------------------------------

                safe_title = (
                    str(title)
                    .replace("/", "_")
                    .replace("\\", "_")
                    .replace("\n", " ")
                    .strip()
                )

                # Prevent excessively long Telegram filename.
                safe_title = safe_title[:150]

                if download_type == "audio":

                    filename = (
                        f"{safe_title}.mp3"
                    )

                    media_type = (
                        "audio/mpeg"
                    )

                else:

                    filename = (
                        f"{safe_title}.mp4"
                    )

                    media_type = (
                        "video/mp4"
                    )

                return {
                    "success": True,
                    "type": download_type,
                    "video_id": video_id,
                    "title": title,
                    "duration": duration,
                    "file_path": existing_file,
                    "filename": filename,
                    "media_type": media_type,
                    "source_url": target_url,
                }

        except Exception as e:

            logger.error(
                f"yt-dlp error: {target_url} | {e}"
            )

            raise RuntimeError(
                f"yt-dlp failed: {str(e)}"
            )
