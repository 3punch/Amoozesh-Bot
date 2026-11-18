"""Extract professor references from Telegram JSON exports and course data."""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

import pandas as pd


def normalize(text: str) -> str:
    """Normalize Persian letters and whitespace for matching."""
    return text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").strip()


def load_professor_names(course_file: str | Path = "courses.xlsx") -> set[str]:
    """Load unique instructor names from the workbook."""
    names: set[str] = set()
    try:
        courses = pd.read_excel(course_file)
    except (OSError, ValueError, ImportError) as exc:
        print(f"Khata dar excel: {exc}")
        return names

    for column in courses.columns:
        if "استاد" not in column and "مدرس" not in column:
            continue
        names.update(
            normalized
            for value in courses[column].dropna().unique()
            if (normalized := normalize(str(value))) and normalized != "نامشخص"
        )
        break
    return names


def _text_from_message(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        fragments = []
        for item in value:
            if isinstance(item, str):
                fragments.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                fragments.append(item["text"])
        return "".join(fragments)
    return ""


def extract_file(
    json_file: str | Path,
    professors: set[str],
    professor_comments: dict[str, list[str]],
) -> None:
    """Read one Telegram export, reporting malformed files without aborting."""
    try:
        with Path(json_file).open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return
        messages = data.get("messages", [])
        if not isinstance(messages, list):
            return

        for message in messages:
            if not isinstance(message, dict) or message.get("type") != "message":
                continue
            text = _text_from_message(message.get("text", ""))
            if len(text.strip()) <= 5:
                continue
            normalized_text = normalize(text)
            clean_text = text.strip().replace("\n", " ")
            for professor in professors:
                parts = professor.split()
                last_name = parts[-1] if len(parts) > 1 else professor
                if len(last_name) > 2 and last_name in normalized_text:
                    comments = professor_comments[professor]
                    if clean_text not in comments:
                        comments.append(clean_text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"Khata dar json {json_file}: {exc}")


def write_profiles(output_file: str | Path, professor_comments: dict[str, list[str]]) -> None:
    """Write up to 25 matched messages for each instructor."""
    with Path(output_file).open("w", encoding="utf-8") as handle:
        for professor, comments in professor_comments.items():
            if not comments:
                continue
            handle.write(f"=== شناسنامه استاد: {professor} ===\n")
            handle.write(f"تعداد نظرات: {len(comments)}\n")
            for index, comment in enumerate(comments[:25], 1):
                handle.write(f"{index}. {comment}\n")
            handle.write("\n" + "=" * 40 + "\n\n")


def main() -> None:
    print("1. In hal sakhte database tamiz...")
    professors = load_professor_names()
    comments = {professor: [] for professor in professors}
    for json_file in glob.glob("*.json"):
        extract_file(json_file, professors, comments)
    write_profiles("structured_professors.txt", comments)
    print("[OK] Database ba movafaghiat sakhte shod (structured_professors.txt)!")


if __name__ == "__main__":
    main()
