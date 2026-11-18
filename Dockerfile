FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && groupadd --system bot \
    && useradd --system --gid bot --create-home bot \
    && mkdir -p /app/.state \
    && chown -R bot:bot /app

# Production entry point and the modules it imports.
COPY EntekhabVahedBot.py api_llm.py deep.py fallback.py llm.py prompts.py quota.py retrieval.py ./
COPY courses.xlsx professors.txt knowledge_base.txt curriculum.pdf ./

USER bot
CMD ["python", "EntekhabVahedBot.py"]
