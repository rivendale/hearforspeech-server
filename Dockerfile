FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HFS_ALLOWED_ORIGINS=https://hearforspeech.com

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir ".[analysis]"

EXPOSE 8000

CMD ["uvicorn", "hearforspeech_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
