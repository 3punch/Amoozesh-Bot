"""تنظیمات ربات آموزش با Pydantic — اعتبارسنجی خودکار متغیرهای محیطی."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator


class TelegramSettings(BaseModel):
    token: str = Field(..., min_length=1, description="توکن ربات تلگرام")
    max_message_len: int = Field(default=4000, gt=0, le=4096)
    parse_mode: str | None = Field(default=None)


class LLMProviderSettings(BaseModel):
    """تنظیمات کلاینت‌های مدل (Ollama و API ابری)."""

    model_name: str = Field(default="qwen2.5:7b")
    ollama_host: str = Field(default="http://127.0.0.1:11434")
    num_ctx: int = Field(default=8192, gt=0)
    max_tokens: int = Field(default=320, gt=0, le=4096)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    timeout: int = Field(default=300, gt=0)
    keep_alive: str = Field(default="6h")
    think: bool = Field(default=False)

    api_key: str | None = Field(default=None)
    api_model: str = Field(default="qwen/qwen-2.5-72b-instruct")
    api_base_url: str = Field(default="https://openrouter.ai/api/v1")
    api_timeout: int = Field(default=120, gt=0)
    api_max_tokens: int = Field(default=700, gt=0, le=4096)

    @field_validator("ollama_host", "api_base_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


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
    limits: dict[str, int] = Field(default={"deep": 3, "api": 1})
    state_path: str = Field(default=".state/quotas.json")
    state_branch: str = Field(default="bot-state")
    state_file: str = Field(default=".state/quotas.json")
    persist: bool = Field(default=True)
    keep_days: int = Field(default=3, gt=0)


class RuntimeSettings(BaseModel):
    run_duration_minutes: float = Field(default=0.0, ge=0)
    model_summary: bool = Field(default=False)
    deep_enabled: bool = Field(default=True)
    pending_ttl: int = Field(default=30 * 60, gt=0)
    pending_max: int = Field(default=400, gt=0)


class BotSettings(BaseModel):
    telegram: TelegramSettings
    llm: LLMProviderSettings
    retrieval: RetrievalSettings
    quota: QuotaSettings
    runtime: RuntimeSettings
    data_dir: Path = Field(default=Path("."))
    log_level: str = Field(default="INFO")

    @model_validator(mode="after")
    def _validate_token_when_runtime(self) -> Any:
        if not self.telegram.token:
            raise ValueError("TELEGRAM_BOT_TOKEN الزامی است")
        return self


def load_settings() -> BotSettings:
    """بارگذاری تنظیمات از متغیرهای محیطی (dotenv پشتیبانی می‌شود)."""
    import os

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:  # pragma: no cover -dotenv اختیاری است
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
            api_key=os.getenv("API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            api_model=os.getenv("API_MODEL", "qwen/qwen-2.5-72b-instruct"),
            api_base_url=os.getenv("API_BASE_URL", "https://openrouter.ai/api/v1"),
            api_timeout=int(os.getenv("API_TIMEOUT", "120")),
            api_max_tokens=int(os.getenv("API_MAX_TOKENS", "700")),
        ),
        retrieval=RetrievalSettings(
            max_context_chars=int(os.getenv("MAX_CONTEXT_CHARS", "4000")),
            max_professor_blocks=int(os.getenv("MAX_PROFESSOR_BLOCKS", "2")),
            max_course_rows=int(os.getenv("MAX_COURSE_ROWS", "5")),
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
        ),
        data_dir=Path(os.getenv("DATA_DIR", ".")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )