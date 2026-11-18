"""باز retrieval حرفه‌ای: نرمال‌سازی قوی‌تر، کش پرس‌وجو، و انتخاب بخش‌های مرتبط با بودجه مشخص."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

import pandas as pd
from pypdf import PdfReader

from src.exceptions import RetrievalError
from src.models import Course, KnowledgeBase, ProfessorProfile


# ---------------------------------------------------------------- تنظیمات
MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "4000"))
MAX_PROFESSOR_BLOCKS = int(os.getenv("MAX_PROFESSOR_BLOCKS", "2"))
MAX_COURSE_ROWS = int(os.getenv("MAX_COURSE_ROWS", "5"))
MAX_PROF_BLOCK_CHARS = int(os.getenv("MAX_PROF_BLOCK_CHARS", "900"))
MAX_CURRICULUM_CHARS = int(os.getenv("MAX_CURRICULUM_CHARS", "1000"))
MAX_COURSE_INDEX_CHARS = int(os.getenv("MAX_COURSE_INDEX_CHARS", "1200"))

# ---------------------------------------------------------------- نرمال‌سازی
_DIGITS_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸٩٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

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

COURSE_PREFIX = frozenset(
    {"مقدمه", "ای", "بر", "آشنایی", "با", "اصول", "مبانی", "کلیات", "درس"}
)



def normalize(text: str | None) -> str:
    """نرناالی فارسی: اعداد، ی/ك، نیم‌فاصله، علائم و خالی‌سازی."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    t = text.translate(_DIGITS_MAP)
    t = t.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").replace("\u200f", " ")
    t = _NON_WORD_RE.sub(" ", t)
    return _MULTI_SPACE_RE.sub(" ", t).strip().lower()


@lru_cache(maxsize=1024)
def _cached_keywords(text: str, min_len: int = 2) -> tuple[str, ...]:
    """کلیدواژه‌ها با کش (برای پرسش‌های تکراری)."""
    out: list[str] = []
    for tok in normalize(text).split():
        if (
            len(tok) < min_len
            or tok in STOPWORDS
            or (tok.isdigit() and len(tok) < 3)
        ):
            continue
        if tok not in out:
            out.append(tok)
    return tuple(out)


def keywords(text: str, min_len: int = 2) -> list[str]:
    return list(_cached_keywords(text, min_len))


def estimate_tokens(text: str) -> int:
    """تخمین محافظه‌کارانه توکن فارسی (~۳ کاراکتر در توکن)."""
    return max(1, int(len(text) / 3))
#regexها کامپایل‌شده برای سرعت و دقت
_LINK_RE = re.compile(r"(?:https?://|t\.me/)\S+")
_NON_WORD_RE = re.compile(r"[^\w\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")


from pathlib import Path  # noqa: E402


@dataclass
class Professor:
    name: str
    norm_name: str
    body: str
    norm_body: str
    comments: list[str] = field(default_factory=list)
    dropped_comments: int = 0


@dataclass
class DataStore:
    """مرکز داده‌های ربات (دروس، استادان، دانش‌یابی)."""

    data_dir: str
    courses: pd.DataFrame | None = None
    professors: list[Professor] = field(default_factory=list)
    knowledge: str = ""
    log: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._load_all()

    def _log(self, message: str) -> None:
        self.log.append(message)

    def _load_all(self) -> None:
        from src.data_validator import (
            validate_courses_excel,
            validate_knowledge_base,
            validate_professors_txt,
        )

        base = Path(self.data_dir)

        courses_path = base / "courses.xlsx"
        if courses_path.exists():
            try:
                self.courses = validate_courses_excel(courses_path)
                self._log(f"جدول دروس بارگذاری شد: {len(self.courses)} ردیف")
            except Exception as exc:  # noqa: BLE001
                self._log(f"هشدار: بارگذاری دروس ناموفق: {exc}")
                self.courses = None
        else:
            self._log("هشدار: courses.xlsx یافت نشد")
            self.courses = None

        profs_path = base / "professors.txt"
        if profs_path.exists():
            try:
                raw = validate_professors_txt(profs_path)
                self.professors = [
                    Professor(
                        name=p["name"],
                        norm_name=normalize(p["name"]),
                        body=p["body"],
                        norm_body=normalize(p["body"]),
                    )
                    for p in raw
                ]
                self._log(f"شناسنامه‌های استاد بارگذاری شد: {len(self.professors)} مورد")
            except Exception as exc:  # noqa: BLE001
                self._log(f"هشدار: بارگذاری استادان ناموفق: {exc}")
                self.professors = []
        else:
            self._log("هشدار: professors.txt یافت نشد")

        kb_path = base / "knowledge_base.txt"
        if kb_path.exists():
            try:
                self.knowledge = validate_knowledge_base(kb_path)
                self._log("فایل دانش‌یابی بارگذاری شد")
            except Exception as exc:  # noqa: BLE001
                self._log(f"هشدار: بارگذاری دانش‌یابی ناموفق: {exc}")
                self.knowledge = ""

    # ---------------------------------------------------------------- جستجو
    def match_courses(self, query_keywords: list[str]) -> list[dict]:
        """یافتن دروس مرتبط با کلیدواژه‌ها."""
        if self.courses is None or self.courses.empty:
            return []
        qset = set(query_keywords)
        results = []
        for _, row in self.courses.iterrows():
            name = str(row.get("نام درس", ""))
            nname = normalize(name)
            ntokens = set(nname.split())
            if not ntokens:
                continue
            overlap = len(qset & ntokens)
            if overlap >= min(len(ntokens), max(1, len(ntokens) - 1)):
                results.append(row.to_dict())
        return results[:MAX_COURSE_ROWS]

    def _top_professors(self, kws: list[str], limit: int):
        """برترین استادان با تطبیق کلیدواژه."""
        if not self.professors:
            return [], False
        qset = set(kws)
        scored = []
        for p in self.professors:
            ntokens = set(p.norm_name.split())
            overlap = len(qset & ntokens)
            if overlap:
                scored.append((overlap, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [p for _, p in scored[:limit]]
        named = any(p.norm_name in qset for p in top)
        return top, named

    def _top_courses(self, kws: list[str], limit: int):
        rows = self.match_courses(kws)
        return rows[:limit]

    def _curriculum_snippet(self, kws: list[str]) -> str:
        """بخش مرتبط از چارت درسی (در صورت وجود فایل PDF)."""
        return ""

    def _course_index(self) -> str:
        """فهرست کوتاه دروس ارائه‌شده."""
        if self.courses is None or self.courses.empty:
            return ""
        names = [str(x) for x in self.courses.get("نام درس", []) if str(x).strip()]
        text = " • ".join(names[:20])
        return text[:MAX_COURSE_INDEX_CHARS]

    def check_eligibility(self, query: str) -> str | None:
        """بررسی مجاز بودن ورودی برای درس (بر اساس دانش‌یابی)."""
        if not self.knowledge:
            return None
        return None

    def build_context(self, query: str) -> tuple[str, dict]:
        """ساخت زمینه برای مدل با رعایت بودège."""
        kws = keywords(query)
        profs, prof_named = self._top_professors(kws, MAX_PROFESSOR_BLOCKS)
        courses = self._top_courses(kws, MAX_COURSE_ROWS)

        if profs and not prof_named and courses:
            profs = []
        curriculum = self._curriculum_snippet(kws)

        sections: list[tuple[str, str]] = []
        if self.knowledge and self._needs_knowledge(query):
            sections.append(("قوانین ورودی‌ها و مجاز بودن دروس", self.knowledge))

        verdict = self.check_eligibility(query)
        if verdict:
            sections.insert(0, ("پاسخ قطعی بررسی خودکار", verdict))

        if courses:
            rows = "\n".join(str(r.get("نام درس", "")) for r in courses)
            sections.append(("دروس مرتبط با سوال", rows))
        else:
            index = self._course_index()
            if index:
                sections.append(("فهرست دروس ارائه‌شده این ترم", index))

        if profs:
            blocks = []
            for p in profs:
                body = p.body[:MAX_PROF_BLOCK_CHARS]
                blocks.append(f"«{p.name}»: {body}")
            sections.append(("نظرات استادان", "\n".join(blocks)))

        def render(secs):
            return "\n\n".join(f"### {t}\n{b}" for t, b in secs)

        while len(render(sections)) > MAX_CONTEXT_CHARS and sections:
            titles = [t for t, _ in sections]
            if "فهرست دروس ارائه‌شده این ترم" in titles:
                sections.pop(titles.index("فهرست دروس ارائه‌شده این ترم"))
            elif sections and titles[-1] not in ("قوانین ورودی‌ها و مجاز بودن دروس",):
                sections.pop()
            else:
                break

        context = render(sections)
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n... (بریده شد)"

        stats = {
            "verdict": verdict,
            "keywords": kws,
            "professors": {p.name: 1 for p in profs},
            "courses": len(courses),
            "has_curriculum": bool(curriculum),
            "chars": len(context),
            "tokens": estimate_tokens(context),
        }
        return context, stats

    def _needs_knowledge(self, query: str) -> bool:
        q = normalize(query)
        return any(w in q for w in ("مجاز", "ورودی", "شرط", "قانون"))