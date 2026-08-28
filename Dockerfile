FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg for yt-dlp audio/video extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables defaults
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

EXPOSE 8000

# Script to run both FastAPI server and Telegram bot concurrently
RUN echo '#!/bin/bash\npython api_server.py & \npython bot.py' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
