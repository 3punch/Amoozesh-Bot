"""مدل‌های داده Pydantic برای ربات آموزش (نوع-βایمن و خوداعتبار)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Course(BaseModel):
    """یک درس ارائه‌شده این ترم."""

    name: str
    instructor: str | None = None
    day: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    capacity: int | None = None
    eligible_inputs: list[str] = Field(default_factory=list)
    term: str | None = None
    raw: dict = Field(default_factory=dict)

    @field_validator("name", "instructor")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v else v

    @field_validator("eligible_inputs", mode="before")
    @classmethod
    def _normalize_inputs(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return [str(v).strip()]


class ProfessorProfile(BaseModel):
    """شناسنامه استخراج‌شده‌ی استاد."""

    name: str
    archive_messages: int = 0
    positive: int = 0
    negative: int = 0
    average_score: float | None = None
    scores: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    dropped_comments: int = 0
    courses: list[str] = Field(default_factory=list)

    class Config:
        extra = "ignore"


class KnowledgeBase(BaseModel):
    """قوانین ورودی و مجاز بودن دروس."""

    rules: str
    source_file: str = "knowledge_base.txt"


class BotResponse(BaseModel):
    """پاسخ نهایی ربات به کاربر."""

    text: str
    source: str = Field(default="fallback")  # fallback | deep | api
    model_used: str | None = None
    elapsed_seconds: float | None = None
    quota_remaining: str | None = None
    metadata: dict = Field(default_factory=dict)