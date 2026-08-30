FROM python:3.11-slim

WORKDIR /app

# System dependencies
# FFmpeg is required by yt-dlp for audio extraction/conversion.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Application
COPY . .

# Railway provides PORT automatically.
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

# Start API + Telegram bot
RUN printf '#!/bin/sh\n\
set -e\n\
\n\
echo "Starting Music API..."\n\
python -m uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000} &\n\
API_PID=$!\n\
\n\
echo "Starting Telegram Bot..."\n\
python bot.py &\n\
BOT_PID=$!\n\
\n\
trap "kill $API_PID $BOT_PID 2>/dev/null || true" TERM INT\n\
\n\
wait -n $API_PID $BOT_PID\n\
STATUS=$?\n\
\n\
kill $API_PID $BOT_PID 2>/dev/null || true\n\
exit $STATUS\n' > /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
