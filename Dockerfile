FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

# Start API and Telegram Bot

CMD ["sh", "-c", "if [ -n \"$YT_API_COOKIES_B64\" ]; then printf '%s' \"$YT_API_COOKIES_B64\" | base64 -d > /app/cookies.txt && chmod 600 /app/cookies.txt; fi; python -m uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000} & python bot.py"]
