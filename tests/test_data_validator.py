from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from amoozesh_bot.data_validator import (
    validate_courses_excel,
    validate_knowledge_base,
    validate_professors_txt,
)
from amoozesh_bot.exceptions import DataValidationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_courses_excel_normalizes_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "courses.xlsx"
    pd.DataFrame(
        {
            "نام درس": ["  ساختمان داده  ", "  ", None],
            "استاد": ["  محمد همامی ", None, None],
            "زمان‌بندی تشکیل کلاس": ["یکشنبه", "", ""],
        }
    ).to_excel(path, index=False)

    courses = validate_courses_excel(path)

    assert len(courses) == 1
    assert courses.iloc[0]["نام درس"] == "ساختمان داده"
    assert courses.iloc[0]["استاد"] == "محمد همامی"


def test_courses_excel_rejects_missing_required_columns(tmp_path: Path) -> None:
    path = tmp_path / "wrong.xlsx"
    pd.DataFrame({"نام درس": ["ریاضی"], "زمان": ["شنبه"]}).to_excel(path, index=False)

    with pytest.raises(DataValidationError, match="استاد"):
        validate_courses_excel(path)


def test_courses_excel_rejects_blank_course_names(tmp_path: Path) -> None:
    path = tmp_path / "blank.xlsx"
    pd.DataFrame({"نام درس": [None, " "], "استاد": ["الف", "ب"]}).to_excel(path, index=False)

    with pytest.raises(DataValidationError, match="ردیف معتبری"):
        validate_courses_excel(path)


def test_professor_parser_reads_repository_format() -> None:
    profiles = validate_professors_txt(REPOSITORY_ROOT / "professors.txt")

    assert len(profiles) == 35
    assert profiles[0]["name"] == "رضا بیات تاجور"
    assert all(profile["name"] and profile["body"] for profile in profiles)


def test_professor_parser_supports_simple_name_blocks(tmp_path: Path) -> None:
    path = tmp_path / "professors.txt"
    path.write_text("name: استاد نمونه\nخوش‌برخورد\n\nنام: استاد دوم\nمنظم", encoding="utf-8")

    profiles = validate_professors_txt(path)

    assert profiles == [
        {"name": "استاد نمونه", "body": "خوش‌برخورد"},
        {"name": "استاد دوم", "body": "منظم"},
    ]


def test_professor_parser_rejects_unrecognized_content(tmp_path: Path) -> None:
    path = tmp_path / "professors.txt"
    path.write_text("این متن قالب شناسنامه ندارد", encoding="utf-8")

    with pytest.raises(DataValidationError, match="شناسنامه‌ی معتبر"):
        validate_professors_txt(path)


def test_knowledge_base_is_trimmed_and_must_not_be_empty(tmp_path: Path) -> None:
    path = tmp_path / "knowledge_base.txt"
    path.write_text("  قوانین انتخاب واحد  \n", encoding="utf-8")
    assert validate_knowledge_base(path) == "قوانین انتخاب واحد"

    path.write_text("  \n", encoding="utf-8")
    with pytest.raises(DataValidationError, match="خالی"):
        validate_knowledge_base(path)


def test_missing_data_file_reports_its_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(DataValidationError) as exc_info:
        validate_knowledge_base(missing)

    assert exc_info.value.source == str(missing)
