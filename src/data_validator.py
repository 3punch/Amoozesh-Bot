"""اعتبارسنجی داده‌های ورودی (Excel/TXT/JSON) قبل از بارگذاری در ربات."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.exceptions import DataValidationError


REQUIRED_COURSE_COLUMNS = {"نام درس", "استاد"}
REQUIRED_PROFESSOR_FIELDS = {"name", "body"}


def validate_courses_excel(path: str | Path) -> pd.DataFrame:
    """فایل lessons را می‌خواند و stunhard اعتبارسنجی می‌کند."""
    path = Path(path)
    if not path.exists():
        raise DataValidationError(f"فایل دروس یافت نشد: {path}", source=str(path))

    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    missing = REQUIRED_COURSE_COLUMNS - set(df.columns)
    if missing:
        raise DataValidationError(
            "ستون‌های ضروری در جدول دروس ندارند: " + ", ".join(sorted(missing)),
            source=str(path),
        )

    # حذف ردیبات خالی کامل
    df = df.dropna(how="all")
    if df.empty:
        raise DataValidationError("جدول دروس خالی است.", source=str(path))

    # نرمال‌سازی نام‌ها
    df["نام درس"] = df["نام درس"].astype(str).str.strip()
    if "استاد" in df.columns:
        df["استاد"] = df["استاد"].astype(str).str.strip()

    return df


def validate_professors_txt(path: str | Path) -> list[dict[str, Any]]:
    """فایل professors.txt را می‌خواند و لیست شناسنامه‌ها را برمی‌گرداند."""
    path = Path(path)
    if not path.exists():
        raise DataValidationError(f"فایل استادان یافت نشد: {path}", source=str(path))

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise DataValidationError("فایل استادان خالی است.", source=str(path))

    # کارشناس انتہایی: هر بلوک با "name:" شروع شود تا بلوک بعدی
    # (مطابق ساختار فعلی ریپو؛ در صورت تغییر، این تابع را آپدیت کنید)
    professors: list[dict[str, Any]] = []
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    for block in blocks:
        lines = block.splitlines()
        name = ""
        body_lines: list[str] = []
        for line in lines:
            if line.startswith("name:") or line.startswith("نام:"):
                name = line.split(":", 1)[1].strip()
            else:
                body_lines.append(line)
        if not name:
            # سعی در استخراج نام از اولین خط غیرخالی
            name = lines[0].strip()[:50] if lines else "نامشخص"
        professors.append({"name": name, "body": "\n".join(body_lines)})

    if not professors:
        raise DataValidationError("هیچ شناسنامهٔ स्टاد معتبری یافت نشد.", source=str(path))

    return professors


def validate_knowledge_base(path: str | Path) -> str:
    """فایل knowledge_base.txt را می‌خواند و محتوای خالی را رد می‌کند."""
    path = Path(path)
    if not path.exists():
        raise DataValidationError(f"فایل دانش‌یابی یافت نشد: {path}", source=str(path))

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise DataValidationError("فایل دانش‌یابی خالی است.", source=str(path))
    return text