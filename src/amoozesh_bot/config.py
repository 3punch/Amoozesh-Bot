"""تنظیمات اعتبارسنجی‌شده‌ی ربات و بارگذاری از محیط یا فایل dotenv."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self


class TelegramSettings(BaseModel):
    token: str = Field(..., min_length=1, description="توکن ربات تلگرام")
    max_message_len: int = Field(default=4000, gt=0, le=4096)
    parse_mode: str | None = None

    @field_validator("token")
    @classmethod
    def _strip_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("توکن تلگرام نباید خالی باشد")
        return token


class LLMProviderSettings(BaseModel):
    """تنظیمات سرویس محلی Ollama و API ابری."""

    model_config = ConfigDict(protected_namespaces=())

    model_name: str = Field(default="qwen2.5:7b", min_length=1)
    ollama_host: str = Field(default="http://127.0.0.1:11434", min_length=1)
    num_ctx: int = Field(default=8192, gt=0)
    max_tokens: int = Field(default=320, gt=0, le=4096)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    timeout: int = Field(default=300, gt=0)
    keep_alive: str = Field(default="6h", min_length=1)
    think: bool = False

    api_key: str | None = None
    api_model: str = Field(default="qwen/qwen-2.5-72b-instruct", min_length=1)
    api_base_url: str = Field(default="https://openrouter.ai/api/v1", min_length=1)
    api_timeout: int = Field(default=120, gt=0)
    api_max_tokens: int = Field(default=700, gt=0, le=4096)

    @field_validator("ollama_host", "api_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.strip().rstrip("/")


class RetrievalSettings(BaseModel):
    max_context_chars: int = Field(default=4000, gt=0)
    max_professor_blocks: int = Field(default=2, gt=0)
    max_course_rows: int = Field(default=5, gt=0)
    max_prof_block_chars: int = Field(default=900, gt=0)
    max_curriculum_chars: int = Field(default=1000, gt=0)
    max_course_index_chars: int = Field(default=1200, gt=0)
    deep_context_chars: int = Field(default=14000, gt=0)
    deep_max_tokens: int = Field(default=500, gt=0, le=2000)
    deep_num_ctx: int = Field(default=8192, gt=0)
    deep_timeout: int = Field(default=900, gt=0)


class QuotaSettings(BaseModel):
    limits: dict[str, int] = Field(default_factory=lambda: {"deep": 3, "api": 1})
    state_path: str = ".state/quotas.json"
    state_branch: str = "bot-state"
    state_file: str = ".state/quotas.json"
    persist: bool = True
    keep_days: int = Field(default=3, gt=0)


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    run_duration_minutes: float = Field(default=0.0, ge=0)
    model_summary: bool = False
    deep_enabled: bool = True
    pending_ttl: int = Field(default=30 * 60, gt=0)
    pending_max: int = Field(default=400, gt=0)


class BotSettings(BaseModel):
    telegram: TelegramSettings
    llm: LLMProviderSettings
    retrieval: RetrievalSettings
    quota: QuotaSettings
    runtime: RuntimeSettings
    data_dir: Path = Field(default=Path("."))
    log_level: str = Field(default="INFO", min_length=1)

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def _validate_token_when_runtime(self) -> Self:
        if not self.telegram.token:
            raise ValueError("TELEGRAM_BOT_TOKEN الزامی است")
        return self


def load_settings() -> BotSettings:
    """بارگذاری تنظیمات محیطی؛ متغیرها نامعتبر باشند، خطا پیش از اجرا رخ می‌دهد."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover - پشتیبانی اختیاری برای نصب حداقلی
        pass

    return BotSettings(
        telegram=TelegramSettings(
            token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            max_message_len=int(os.getenv("MAX_MESSAGE_LEN", "4000")),
        ),
        llm=LLMProviderSettings(
            model_name=os.getenv("MODEL_NAME", "qwen2.5:7b"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
            num_ctx=int(os.getenv("NUM_CTX", "8192")),
            max_tokens=int(os.getenv("MAX_TOKENS", "320")),
            temperature=float(os.getenv("TEMPERATURE", "0.2")),
            timeout=int(os.getenv("LLM_TIMEOUT", "300")),
            keep_alive=os.getenv("OLLAMA_KEEP_ALIVE", "6h"),
            think=os.getenv("THINK", "0") == "1",
            api_key=(
                os.getenv("API_KEY")
                or os.getenv("OPENROUTER_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            ),
            api_model=os.getenv("API_MODEL", "qwen/qwen-2.5-72b-instruct"),
            api_base_url=os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1"),
            api_timeout=int(os.getenv("API_TIMEOUT", "120")),
            api_max_tokens=int(os.getenv("API_MAX_TOKENS", "700")),
        ),
        retrieval=RetrievalSettings(
            max_context_chars=int(os.getenv("MAX_CONTEXT_CHARS", "4000")),
            max_professor_blocks=int(os.getenv("MAX_PROFESSOR_BLOCKS", "2")),
            max_course_rows=int(os.getenv("MAX_COURSE_ROWS", "5")),
            max_prof_block_chars=int(os.getenv("MAX_PROF_BLOCK_CHARS", "900")),
            max_curriculum_chars=int(os.getenv("MAX_CURRICULUM_CHARS", "1000")),
            max_course_index_chars=int(os.getenv("MAX_COURSE_INDEX_CHARS", "1200")),
            deep_context_chars=int(os.getenv("DEEP_CONTEXT_CHARS", "14000")),
            deep_max_tokens=int(os.getenv("DEEP_MAX_TOKENS", "500")),
            deep_num_ctx=int(os.getenv("DEEP_NUM_CTX", "8192")),
            deep_timeout=int(os.getenv("DEEP_TIMEOUT", "900")),
        ),
        quota=QuotaSettings(
            state_path=os.getenv("QUOTA_STATE_PATH", ".state/quotas.json"),
            state_branch=os.getenv("QUOTA_STATE_BRANCH", "bot-state"),
            state_file=os.getenv("QUOTA_STATE_FILE", ".state/quotas.json"),
            persist=os.getenv("QUOTA_PERSIST", "1") != "0",
            keep_days=int(os.getenv("KEEP_DAYS", "3")),
        ),
        runtime=RuntimeSettings(
            run_duration_minutes=float(os.getenv("RUN_DURATION_MINUTES", "0") or 0),
            model_summary=os.getenv("MODEL_SUMMARY", "0") == "1",
            deep_enabled=os.getenv("DEEP_MODE", "1") == "1",
            pending_ttl=int(os.getenv("PENDING_TTL", str(30 * 60))),
            pending_max=int(os.getenv("PENDING_MAX", "400")),
        ),
        data_dir=Path(os.getenv("DATA_DIR", ".")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
