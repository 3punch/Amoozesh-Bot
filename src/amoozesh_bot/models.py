"""مدل‌های داده‌ی اعتبارسنجی‌شده برای سرویس ربات."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Course(BaseModel):
    """یک ارائه‌ی درس در ترم جاری."""

    name: str = Field(min_length=1)
    instructor: str | None = None
    day: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    capacity: int | None = Field(default=None, ge=0)
    eligible_inputs: list[str] = Field(default_factory=list)
    term: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("نام درس نباید خالی باشد")
        return name

    @field_validator("instructor")
    @classmethod
    def _strip_instructor(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("eligible_inputs", mode="before")
    @classmethod
    def _normalize_inputs(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()]


class ProfessorProfile(BaseModel):
    """شناسنامه‌ی خلاصه‌شده‌ی یک استاد."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1)
    archive_messages: int = Field(default=0, ge=0)
    positive: int = Field(default=0, ge=0)
    negative: int = Field(default=0, ge=0)
    average_score: float | None = Field(default=None, ge=0, le=10)
    scores: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    dropped_comments: int = Field(default=0, ge=0)
    courses: list[str] = Field(default_factory=list)


class KnowledgeBase(BaseModel):
    """مجموعه‌ی قوانین انتخاب واحد و محدودیت ورودی‌ها."""

    rules: str = Field(min_length=1)
    source_file: str = "knowledge_base.txt"


class BotResponse(BaseModel):
    """پاسخ نهایی و منشأ آن برای ثبت و آزمون."""

    model_config = ConfigDict(protected_namespaces=())

    text: str = Field(min_length=1)
    source: str = "fallback"
    model_used: str | None = None
    elapsed_seconds: float | None = Field(default=None, ge=0)
    quota_remaining: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
