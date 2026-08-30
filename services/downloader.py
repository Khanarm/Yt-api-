import os
import asyncio
import glob
import tempfile

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

        url = url.strip()

        if not url:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error": "INVALID_URL",
                },
            )

        # Video ID
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
                    f"Download failed: "
                    f"{target_url} | {e}"
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

        os.makedirs(
            download_dir,
            exist_ok=True,
        )

        output_template = os.path.join(
            download_dir,
            "%(id)s.%(ext)s",
        )

        # ======================================================
        # COMMON YT-DLP OPTIONS
        # ======================================================

        ydl_opts = {
            "outtmpl": output_template,

            "quiet": False,
            "no_warnings": False,

            "noplaylist": True,

            # Better network behaviour
            "retries": 3,
            "fragment_retries": 3,

            "socket_timeout": 30,

            # Do not abort immediately on unavailable formats
            "ignoreerrors": False,

            # IPv4 is generally more reliable on many servers
            "forceipv4": True,

            # YouTube extractor configuration
            "extractor_args": {
                "youtube": {
                    "player_client": [
                        "android",
                        "web",
                    ]
                }
            },
        }

        # ======================================================
        # OPTIONAL COOKIES
        # ======================================================
        #
        # If YT_API_COOKIES_FILE is configured in Railway,
        # yt-dlp will use that cookies file.
        #
        # Example Railway variable:
        #
        # YT_API_COOKIES_FILE=/app/cookies.txt
        #
        # Do NOT put cookies directly into this Python file.
        #

        cookies_file = os.environ.get(
            "YT_API_COOKIES_FILE"
        )

        if cookies_file:
            cookies_file = cookies_file.strip()

            if os.path.isfile(cookies_file):

                ydl_opts["cookiefile"] = cookies_file

                logger.info(
                    "YouTube cookies enabled."
                )

            else:

                logger.warning(
                    "YT_API_COOKIES_FILE is set, "
                    "but file does not exist: "
                    f"{cookies_file}"
                )

        # ======================================================
        # AUDIO
        # ======================================================

        if download_type == "audio":

            ydl_opts.update(
                {
                    "format": (
                        "bestaudio/best"
                    ),

                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],

                    "keepvideo": False,
                }
            )

        # ======================================================
        # VIDEO
        # ======================================================

        else:

            ydl_opts.update(
                {
                    "format": (
                        "bestvideo[ext=mp4]+"
                        "bestaudio[ext=m4a]/"
                        "best[ext=mp4]/"
                        "best"
                    ),

                    "merge_output_format": "mp4",
                }
            )

        logger.info(
            f"Starting yt-dlp download | "
            f"type={download_type} | "
            f"url={target_url}"
        )

        # ======================================================
        # DOWNLOAD
        # ======================================================

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

                # ==================================================
                # FIND DOWNLOADED FILE
                # ==================================================

                existing_file = None

                if download_type == "audio":

                    expected = os.path.join(
                        download_dir,
                        f"{video_id}.mp3",
                    )

                else:

                    expected = os.path.join(
                        download_dir,
                        f"{video_id}.mp4",
                    )

                if os.path.isfile(expected):

                    existing_file = expected

                else:

                    matches = glob.glob(
                        os.path.join(
                            download_dir,
                            f"{video_id}.*",
                        )
                    )

                    matches = [
                        x
                        for x in matches
                        if os.path.isfile(x)
                        and not x.endswith(
                            (
                                ".part",
                                ".ytdl",
                            )
                        )
                    ]

                    if matches:

                        existing_file = max(
                            matches,
                            key=os.path.getmtime,
                        )

                if not existing_file:

                    raise RuntimeError(
                        "Downloaded file could not "
                        "be found."
                    )

                # ==================================================
                # SAFE TELEGRAM FILENAME
                # ==================================================

                safe_title = str(
                    title
                )

                safe_title = (
                    safe_title
                    .replace("/", "_")
                    .replace("\\", "_")
                    .replace("\n", " ")
                    .replace("\r", " ")
                    .strip()
                )

                if not safe_title:
                    safe_title = video_id

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

                logger.info(
                    f"Download successful | "
                    f"id={video_id} | "
                    f"title={title} | "
                    f"file={existing_file}"
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

        except yt_dlp.utils.DownloadError as e:

            error_text = str(e)

            logger.error(
                f"yt-dlp DownloadError | "
                f"{target_url} | "
                f"{error_text}"
            )

            # More useful error messages
            if "Please sign in" in error_text:

                raise RuntimeError(
                    "YouTube requires authentication "
                    "for this video. Configure a valid "
                    "YouTube cookies file for yt-dlp."
                )

            if "Sign in to confirm" in error_text:

                raise RuntimeError(
                    "YouTube bot verification requires "
                    "authentication. Configure a valid "
                    "YouTube cookies file for yt-dlp."
                )

            if "Video unavailable" in error_text:

                raise RuntimeError(
                    "YouTube video is unavailable."
                )

            raise RuntimeError(
                f"yt-dlp failed: {error_text}"
            )

        except Exception as e:

            logger.error(
                f"yt-dlp error: "
                f"{target_url} | {repr(e)}"
            )

            raise RuntimeError(
                f"yt-dlp failed: {str(e)}"
            )
