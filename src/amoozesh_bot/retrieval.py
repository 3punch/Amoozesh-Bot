"""بازیابی زمینه‌ی مرتبط از فایل‌های دروس، استادان و چارت آموزشی."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader

from amoozesh_bot.data_validator import (
    validate_courses_excel,
    validate_knowledge_base,
    validate_professors_txt,
)

MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "4000"))
MAX_PROFESSOR_BLOCKS = int(os.getenv("MAX_PROFESSOR_BLOCKS", "2"))
MAX_COURSE_ROWS = int(os.getenv("MAX_COURSE_ROWS", "5"))
MAX_PROF_BLOCK_CHARS = int(os.getenv("MAX_PROF_BLOCK_CHARS", "900"))
MAX_CURRICULUM_CHARS = int(os.getenv("MAX_CURRICULUM_CHARS", "1000"))
MAX_COURSE_INDEX_CHARS = int(os.getenv("MAX_COURSE_INDEX_CHARS", "1200"))

_DIGITS_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸٩٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_NON_WORD_RE = re.compile(r"[^\w\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")
_YEAR_RE = re.compile(r"\b(14[0-9]{2})\b")
_ENTRY_YEAR_RE = re.compile(r"^دروس ویژه دانشجویان ورودی\s*(14[0-9]{2})")

STOPWORDS = frozenset(
    """و در به از که این آن را با برای هم یا اگر چه چی کی کدوم کدام است هست هستند بود شود
    میشه می‌شه بشه کن بکن بگو بگید بگوین لطفا سلام ممنون مرسی بله نه خیر
    استاد استادش استادم استادای اساتید دکتر درس درسش درسم درسه ترم ترمه ترمی
    ارائه ارایه نظر نظرت نظری درباره مورد راجع راجب بهم من تو شما ما اون اینا اینو
    چطوره چطور چطوری خوبه خوب بد چیه نیست هستش داشتم داشته بگیرم بردارم اخذ اخذش
    واحد واحده واحدم چند چندتا کجا کِی کی چرا آیا میخوام می‌خوام میخواستم میشه
    یکی یه یه‌کم خیلی بچه بچه‌ها بچه ها دوستان کسی کسی‌ میدونه می‌دونه بدونم بگین
    اطلاعات راهنمایی کمک لطفاً دوست داشتم داشتید دارید کردم کردم کدام ای
    کلاس کیه چیه چطور استادی استادیه استادش هستن هستید چجور چجوری بگی بگه کسی بچه""".split()
)
COURSE_PREFIX = frozenset({"مقدمه", "ای", "بر", "آشنایی", "با", "اصول", "مبانی", "کلیات", "درس"})
_LINK_RE = re.compile(r"(?:https?://|t\.me/)\S+")


def normalize(text: str | None) -> str:
    """نرمال‌سازی فارسی: اعداد، ی/ک، نیم‌فاصله و فاصله‌گذاری."""
    if text is None:
        return ""
    normalized = str(text).translate(_DIGITS_MAP)
    normalized = normalized.replace("ي", "ی").replace("ك", "ک")
    normalized = normalized.replace("\u200c", " ").replace("\u200f", " ")
    normalized = _NON_WORD_RE.sub(" ", normalized)
    return _MULTI_SPACE_RE.sub(" ", normalized).strip().lower()


@lru_cache(maxsize=1024)
def _cached_keywords(text: str, min_len: int = 2) -> tuple[str, ...]:
    words: list[str] = []
    for token in normalize(text).split():
        if len(token) < min_len or token in STOPWORDS:
            continue
        if token.isdigit() and len(token) < 3:
            continue
        if token not in words:
            words.append(token)
    return tuple(words)


def keywords(text: str, min_len: int = 2) -> list[str]:
    """کلیدواژه‌های نرمال‌شده‌ی پرسش، با حذف کلمات پرتکرار."""
    return list(_cached_keywords(text, min_len))


def estimate_tokens(text: str) -> int:
    """تخمین محافظه‌کارانه‌ی توکن برای متن فارسی."""
    return max(1, len(text) // 3)


@dataclass
class Professor:
    """نمایش سبک از یک شناسنامه‌ی استاد."""

    name: str
    norm_name: str
    body: str
    norm_body: str
    comments: list[str] = field(default_factory=list)
    dropped_comments: int = 0


@dataclass
class DataStore:
    """مخزن خواندنی داده‌های محلی پروژه؛ فایل نامعتبر بی‌صدا پنهان نمی‌شود."""

    data_dir: str | Path = "."
    courses: pd.DataFrame | None = field(default=None, init=False)
    professors: list[Professor] = field(default_factory=list, init=False)
    knowledge: str = field(default="", init=False)
    curriculum: str = field(default="", init=False)
    entry_rules: dict[str, set[str]] = field(default_factory=dict, init=False)
    log: list[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir)
        self._load_all()

    def _log(self, message: str) -> None:
        self.log.append(message)

    def _load_all(self) -> None:
        base = Path(self.data_dir)

        courses_path = base / "courses.xlsx"
        if courses_path.exists():
            try:
                self.courses = validate_courses_excel(courses_path)
                self._log(f"جدول دروس بارگذاری شد: {len(self.courses)} ردیف")
            except Exception as exc:
                self._log(f"هشدار: بارگذاری دروس ناموفق: {exc}")
        else:
            self._log("هشدار: courses.xlsx یافت نشد")

        professors_path = base / "professors.txt"
        if professors_path.exists():
            try:
                profiles = validate_professors_txt(professors_path)
                self.professors = [
                    Professor(
                        name=profile["name"],
                        norm_name=normalize(profile["name"]),
                        body=profile["body"],
                        norm_body=normalize(profile["body"]),
                    )
                    for profile in profiles
                ]
                self._log(f"شناسنامه‌های استاد بارگذاری شد: {len(self.professors)} مورد")
            except Exception as exc:
                self._log(f"هشدار: بارگذاری استادان ناموفق: {exc}")
        else:
            self._log("هشدار: professors.txt یافت نشد")

        knowledge_path = base / "knowledge_base.txt"
        if knowledge_path.exists():
            try:
                self.knowledge = validate_knowledge_base(knowledge_path)
                self._parse_entry_rules()
                self._log(f"قوانین ورودی‌ها بارگذاری شد: {len(self.entry_rules)} درس محدود")
            except Exception as exc:
                self._log(f"هشدار: بارگذاری دانش‌یابی ناموفق: {exc}")

        curriculum_path = base / "curriculum.pdf"
        if curriculum_path.exists():
            try:
                reader = PdfReader(str(curriculum_path))
                self.curriculum = "\n".join(
                    page.extract_text() or "" for page in reader.pages
                ).strip()
                self._log(f"چارت درسی بارگذاری شد: {len(self.curriculum)} کاراکتر")
            except Exception as exc:
                self._log(f"هشدار: بارگذاری چارت درسی ناموفق: {exc}")

    def _parse_entry_rules(self) -> None:
        """استخراج محدودیت‌های ورودی از عنوان بخش‌ها در دانش‌نامه."""
        current_year: str | None = None
        for raw_line in self.knowledge.splitlines():
            raw_line = raw_line.strip()
            line = normalize(raw_line)
            year_match = _ENTRY_YEAR_RE.match(line)
            if year_match:
                current_year = year_match.group(1)
                continue
            if line.startswith("دروسی که"):
                current_year = None
                continue
            if current_year and " - " in raw_line:
                course_name = normalize(raw_line.split(" - ", 1)[0])
                if course_name:
                    self.entry_rules.setdefault(course_name, set()).add(current_year)

    def match_courses(self, query_keywords: list[str]) -> list[dict[str, Any]]:
        """رتبه‌بندی ارائه‌ها بر اساس هم‌پوشانی نام درس و پرسش."""
        if self.courses is None or self.courses.empty or not query_keywords:
            return []

        query_terms = set(query_keywords)
        scored: list[tuple[int, dict[str, Any]]] = []
        for _, row in self.courses.iterrows():
            name_terms = set(normalize(str(row.get("نام درس", ""))).split())
            instructor_terms = set(normalize(str(row.get("استاد", ""))).split())
            name_hits = query_terms & name_terms
            instructor_hits = query_terms & instructor_terms
            score = 3 * len(name_hits) + 2 * len(instructor_hits)
            if score:
                row_data = {str(key): value for key, value in row.to_dict().items()}
                scored.append((score, row_data))
        scored.sort(key=lambda result: result[0], reverse=True)
        return [row for _, row in scored[:MAX_COURSE_ROWS]]

    def _top_professors(self, query_terms: list[str], limit: int) -> tuple[list[Professor], bool]:
        if not self.professors or not query_terms:
            return [], False

        owners: dict[str, int] = {}
        for professor in self.professors:
            for term in set(professor.norm_name.split()):
                owners[term] = owners.get(term, 0) + 1

        query_set = set(query_terms)
        ranked: list[tuple[int, Professor, bool]] = []
        for professor in self.professors:
            name_terms = set(professor.norm_name.split())
            name_hits = query_set & name_terms
            body_hits = sum(min(professor.norm_body.count(term), 4) for term in query_terms)
            distinctive_name_hit = any(owners.get(term) == 1 for term in name_hits)
            score = 12 * len(name_hits) + body_hits
            if score:
                ranked.append((score, professor, distinctive_name_hit))

        ranked.sort(key=lambda item: item[0], reverse=True)
        named_matches = [item for item in ranked if item[2]]
        candidates = named_matches or ranked
        return [item[1] for item in candidates[:limit]], bool(named_matches)

    def _top_courses(self, query_terms: list[str], limit: int) -> list[dict[str, Any]]:
        return self.match_courses(query_terms)[:limit]

    def _curriculum_snippet(self, query_terms: list[str]) -> str:
        if not self.curriculum or not query_terms:
            return ""
        matching_lines = [
            line.strip()
            for line in self.curriculum.splitlines()
            if any(term in normalize(line) for term in query_terms)
        ]
        return "\n".join(matching_lines)[:MAX_CURRICULUM_CHARS]

    def _course_index(self) -> str:
        if self.courses is None or self.courses.empty:
            return ""
        names = dict.fromkeys(
            str(name).strip() for name in self.courses["نام درس"] if str(name).strip()
        )
        return " • ".join(names)[:MAX_COURSE_INDEX_CHARS]

    def eligibility_info(self, query: str) -> dict[str, Any] | None:
        """پاسخ قطعی برای پرسش درس + سال ورودی؛ None اگر داده کافی نیست."""
        normalized_query = normalize(query)
        years = _YEAR_RE.findall(normalized_query)
        if not years:
            return None

        candidates = set(self.entry_rules)
        if self.courses is not None:
            candidates.update(
                normalize(str(name)) for name in self.courses["نام درس"] if str(name).strip()
            )

        course_name = max(
            (name for name in candidates if len(name) > 3 and name in normalized_query),
            key=len,
            default="",
        )
        if not course_name:
            query_terms = set(normalized_query.split())
            for candidate in candidates:
                core_terms = [term for term in candidate.split() if term not in COURSE_PREFIX]
                if len(core_terms) >= 2 and set(core_terms).issubset(query_terms):
                    if len(candidate) > len(course_name):
                        course_name = candidate
        if not course_name:
            return None

        year = years[0]
        restricted_years = sorted(self.entry_rules.get(course_name, set()))
        allowed = not restricted_years or year in restricted_years
        reason = (
            f"این درس ویژه‌ی ورودی‌های {'، '.join(restricted_years)} است."
            if restricted_years
            else "در فایل قوانین، محدودیت ورودی برای این درس ثبت نشده است."
        )
        return {
            "course": course_name,
            "year": year,
            "allowed": allowed,
            "restricted_to": restricted_years,
            "reason": reason,
        }

    def check_eligibility(self, query: str) -> str:
        """نتیجه‌ی مجاز بودن درس را از قوانین محلی می‌سازد، نه از حدس مدل."""
        info = self.eligibility_info(query)
        if info is None:
            return ""
        verdict = "مجاز است" if info["allowed"] else "مجاز نیست"
        return f"«{info['course']}» برای ورودی {info['year']} {verdict} ({info['reason']})"

    def _needs_knowledge(self, query: str) -> bool:
        normalized = normalize(query)
        return bool(_YEAR_RE.search(normalized)) or any(
            word in normalized for word in ("ورودی", "مجاز", "شرط", "قانون", "ظرفیت")
        )

    def build_context(self, query: str) -> tuple[str, dict[str, Any]]:
        """زمینه‌ی مرتبط را با حفظ پاسخ قطعی و رعایت سقف کاراکتر می‌سازد."""
        query_terms = keywords(query)
        professors, professor_named = self._top_professors(query_terms, MAX_PROFESSOR_BLOCKS)
        courses = self._top_courses(query_terms, MAX_COURSE_ROWS)
        if professors and not professor_named and courses:
            professors = []

        sections: list[tuple[str, str]] = []
        if self.knowledge and self._needs_knowledge(query):
            sections.append(("قوانین ورودی‌ها و مجاز بودن دروس", self.knowledge))

        verdict = self.check_eligibility(query)
        if verdict:
            sections.insert(0, ("پاسخ قطعی بررسی خودکار", verdict))

        if courses:
            rows = "\n".join(
                f"{row.get('نام درس', '')} | {row.get('استاد', '')} | "
                f"{row.get('زمان‌بندی تشکیل کلاس', '')}"
                for row in courses
            )
            sections.append(("ارائه‌های مرتبط این ترم", rows))
        else:
            course_index = self._course_index()
            if course_index:
                sections.append(("فهرست دروس ارائه‌شده این ترم", course_index))

        if professors:
            professor_blocks = [
                f"«{professor.name}»: {professor.body[:MAX_PROF_BLOCK_CHARS]}"
                for professor in professors
            ]
            sections.append(("نظرها و اطلاعات استادان مرتبط", "\n\n".join(professor_blocks)))

        curriculum = self._curriculum_snippet(query_terms)
        if curriculum:
            sections.append(("بخش مرتبط از چارت درسی", curriculum))

        def render(parts: list[tuple[str, str]]) -> str:
            return "\n\n".join(f"### {title}\n{body}" for title, body in parts)

        while len(render(sections)) > MAX_CONTEXT_CHARS and sections:
            removable = next(
                (
                    index
                    for index in range(len(sections) - 1, -1, -1)
                    if sections[index][0] != "پاسخ قطعی بررسی خودکار"
                ),
                None,
            )
            if removable is None:
                break
            sections.pop(removable)

        context = render(sections)
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS].rstrip() + "\n… (بخش‌های پایانی کوتاه شد)"

        return context, {
            "verdict": verdict,
            "keywords": query_terms,
            "professors": {professor.name: 1 for professor in professors},
            "courses": len(courses),
            "has_curriculum": bool(curriculum),
            "chars": len(context),
            "tokens": estimate_tokens(context),
        }
