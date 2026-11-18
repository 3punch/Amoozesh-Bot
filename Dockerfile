# ==============================================================================
# Amoozesh-Bot — Dockerfile حرفه‌ای (multi-stage نیست چون چند به‌هم نیstadند)
# ==============================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# وابستگی‌های سیستم (برای pandas/openpyxl/pypdf و telegram)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
        libjpeg-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# فایل وابستگی‌ها
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# کد پروژه
COPY src ./src
COPY pyproject.toml ./
COPY README.md ./
COPY .env.example ./

# دیتا و حالت (حجم داشته باشد، اینجا فقط خالی می‌سازیم؛ در اجرا volume می‌گیرد)
RUN mkdir -p .state data

# متغیرهای پیش‌فرض (از .env در زمان اجراณ์ است)
ENV TELEGRAM_BOT_TOKEN="" \
    MODEL_NAME="qwen2.5:7b" \
    OLLAMA_HOST="http://host.docker.internal:11434" \
    LOG_LEVEL="INFO"

EXPOSE 8080

CMD ["python", "EntekhabVahedBot.py"]