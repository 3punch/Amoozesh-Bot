"""اعتبارسنجی و پاک‌سازی فایل‌های ورودی ربات پیش از استفاده."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from amoozesh_bot.exceptions import DataValidationError

REQUIRED_COURSE_COLUMNS = {"نام درس", "استاد"}
REQUIRED_PROFESSOR_FIELDS = {"name", "body"}
PROFESSOR_HEADER_RE = re.compile(r"^===\s*شناسنامه استاد:\s*(?P<name>.+?)\s*===$", re.MULTILINE)


def validate_courses_excel(path: str | Path) -> pd.DataFrame:
    """جدول دروس را می‌خواند؛ ستون‌ها و نام درس‌های خالی را اعتبارسنجی می‌کند."""
    source = Path(path)
    if not source.is_file():
        raise DataValidationError(f"فایل دروس یافت نشد: {source}", source=str(source))

    try:
        courses = pd.read_excel(source, engine="openpyxl")
    except (OSError, ValueError, ImportError) as exc:
        raise DataValidationError(
            f"خواندن فایل دروس ناموفق بود: {exc}", source=str(source)
        ) from exc

    courses.columns = [str(column).strip() for column in courses.columns]
    missing = REQUIRED_COURSE_COLUMNS - set(courses.columns)
    if missing:
        raise DataValidationError(
            "ستون‌های ضروری در جدول دروس وجود ندارند: " + ", ".join(sorted(missing)),
            source=str(source),
        )

    courses = courses.dropna(how="all").copy()
    courses["نام درس"] = courses["نام درس"].fillna("").astype(str).str.strip()
    courses = courses.loc[courses["نام درس"].ne("")].copy()
    if courses.empty:
        raise DataValidationError("جدول دروس ردیف معتبری ندارد.", source=str(source))

    courses["استاد"] = courses["استاد"].fillna("").astype(str).str.strip()
    return courses


def _records_from_headers(text: str) -> list[dict[str, str]]:
    """قالب فعلی professors.txt را با مرزبندی headerهای واقعی می‌خواند."""
    headers = list(PROFESSOR_HEADER_RE.finditer(text))
    records: list[dict[str, str]] = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[header.end() : end]
        body = re.sub(r"^=+\s*$", "", body, flags=re.MULTILINE)
        body = re.sub(r"^\s*تعداد نظرات:.*$", "", body, flags=re.MULTILINE)
        body = re.sub(r"\n{2,}", "\n", body).strip()
        records.append({"name": header.group("name").strip(), "body": body})
    return records


def _records_from_fields(text: str) -> list[dict[str, str]]:
    """پشتیبانی از قالب ساده‌ی name:/نام: و بلوک‌های جداشده با خط خالی."""
    records: list[dict[str, str]] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        name = ""
        body_lines: list[str] = []
        for line in lines:
            if line.startswith(("name:", "نام:")):
                name = line.split(":", 1)[1].strip()
            else:
                body_lines.append(line)
        if name:
            records.append({"name": name, "body": "\n".join(body_lines).strip()})
    return records


def validate_professors_txt(path: str | Path) -> list[dict[str, Any]]:
    """شناسنامه‌ها را از قالب فعلی یا قالب name:/نام: استخراج می‌کند."""
    source = Path(path)
    if not source.is_file():
        raise DataValidationError(f"فایل استادان یافت نشد: {source}", source=str(source))

    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DataValidationError(
            f"خواندن فایل استادان ناموفق بود: {exc}", source=str(source)
        ) from exc
    if not text.strip():
        raise DataValidationError("فایل استادان خالی است.", source=str(source))

    records = _records_from_headers(text) or _records_from_fields(text)
    valid = [
        record
        for record in records
        if REQUIRED_PROFESSOR_FIELDS.issubset(record)
        and record["name"].strip()
        and record["body"].strip()
    ]
    if not valid:
        raise DataValidationError(
            "هیچ شناسنامه‌ی معتبری در فایل استادان پیدا نشد.", source=str(source)
        )
    return valid


def validate_knowledge_base(path: str | Path) -> str:
    """متن قوانین را با encoding درست می‌خواند و محتوای خالی را رد می‌کند."""
    source = Path(path)
    if not source.is_file():
        raise DataValidationError(f"فایل دانش‌یابی یافت نشد: {source}", source=str(source))

    try:
        text = source.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        raise DataValidationError(
            f"خواندن فایل دانش‌یابی ناموفق بود: {exc}", source=str(source)
        ) from exc
    if not text:
        raise DataValidationError("فایل دانش‌یابی خالی است.", source=str(source))
    return text
