"""
آماده‌سازی «زمینه» (context) برای مدل محلی.

مدل‌های کوچک مثل gemma3:4b فقط چند هزار توکن زمینه را به‌خوبی مدیریت می‌کنند،
بنابراین به‌جای ریختن کل دیتا در پرامپت (که در نسخه‌ی قبلی ~۱۸۰هزار کاراکتر می‌شد)
فقط مرتبط‌ترین بخش‌ها انتخاب و با بودجه‌ی مشخص بریده می‌شوند.

متغیرهای محیطی:
    MAX_CONTEXT_CHARS     سقف کل متن زمینه        (پیش‌فرض: 9000)
    MAX_PROFESSOR_BLOCKS  حداکثر شناسنامه‌ی استاد  (پیش‌فرض: 3)
    MAX_COURSE_ROWS       حداکثر ردیف درس          (پیش‌فرض: 8)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import pandas as pd
from pypdf import PdfReader

MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "9000"))
MAX_PROFESSOR_BLOCKS = int(os.getenv("MAX_PROFESSOR_BLOCKS", "3"))
MAX_COURSE_ROWS = int(os.getenv("MAX_COURSE_ROWS", "8"))
MAX_PROF_BLOCK_CHARS = 1400
MAX_CURRICULUM_CHARS = 1000
MAX_COURSE_INDEX_CHARS = 1200

# ---------------------------------------------------------------- نرمال‌سازی

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

STOPWORDS = set(
    """و در به از که این آن را با برای هم یا اگر چه چی کی کدوم کدام است هست هستند بود شود
    میشه می‌شه بشه کن بکن بگو بگید بگوین لطفا سلام ممنون مرسی بله نه خیر
    استاد استادش استادم استادای اساتید دکتر درس درسش درسم درسه ترم ترمه ترمی
    ارائه ارایه نظر نظرت نظری درباره مورد راجع راجب بهم من تو شما ما اون اینا اینو
    چطوره چطور چطوری خوبه خوب بد چیه نیست هستش داشتم داشته بگیرم بردارم اخذ اخذش
    واحد واحده واحدم چند چندتا کجا کِی کی چرا آیا میخوام می‌خوام میخواستم میشه
    یکی یه یه‌کم خیلی بچه بچه‌ها بچه ها دوستان کسی کسی‌ میدونه می‌دونه بدونم بگین
    اطلاعات راهنمایی کمک لطفاً دوست داشتم داشتید دارید کردم کردم کدام
    استادی استادیه استادش هستن هستید چجور چجوری بگی بگه ریاضی کسی بچه""".split()
)


def normalize(text) -> str:
    """ی/ك عربی، نیم‌فاصله، اعداد فارسی و علائم را یکدست می‌کند."""
    if not isinstance(text, str):
        if text is None:
            return ""
        text = str(text)
    t = text.translate(_DIGITS)
    t = t.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").replace("\u200f", " ")
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def keywords(text: str, min_len: int = 2) -> list[str]:
    out: list[str] = []
    for tok in normalize(text).split():
        if len(tok) < min_len or tok in STOPWORDS or tok.isdigit() and len(tok) < 3:
            continue
        if tok not in out:
            out.append(tok)
    return out


def estimate_tokens(text: str) -> int:
    """تخمین محافظه‌کارانه برای فارسی (~۳ کاراکتر در هر توکن)."""
    return int(len(text) / 3)


# ---------------------------------------------------------------- بارگذاری


@dataclass
class Professor:
    name: str
    norm_name: str
    body: str
    norm_body: str
    comments: list[str] = field(default_factory=list)
    dropped_comments: int = 0


LINK_RE = re.compile(r"(?:https?://|t\.me/)\S+")


def is_link_spam(text: str) -> bool:
    """پیام‌هایی که فهرست لینک گروه/کانال‌اند و ارزش اطلاعاتی ندارند."""
    links = LINK_RE.findall(text)
    if not links:
        return False
    # دو لینک یا بیشتر ⇒ قطعاً «لیست لینک» است، نه ارزیابی استاد
    if len(links) >= 2:
        return True
    stripped = LINK_RE.sub(" ", text)
    words = [w for w in re.sub(r"[^\w\s]", " ", stripped).split() if len(w) > 2]
    return len(" ".join(words)) < 60


def clean_comments(body: str) -> tuple[list[str], int]:
    """نظرات مفید را جدا می‌کند؛ خروجی: (نظرات، تعداد پیام‌های حذف‌شده)."""
    kept: list[str] = []
    dropped = 0
    for line in body.splitlines():
        m = re.match(r"^\s*\d+\.\s*(.*)$", line)
        text = (m.group(1) if m else line).strip()
        if not text or set(text) <= {"=", " "} or text == "نظر مفیدی ثبت نشده است.":
            continue
        if is_link_spam(text):
            dropped += 1
            continue
        # حذف تبلیغ ربات/کانال که انتهای فرم‌های استادشناسی چسبیده است
        text = re.split(r"برای ارسال فرم|@tahqiqat_bot|کانال استاد شناسی", text)[0]
        text = re.sub(r"\s{2,}", " ", LINK_RE.sub("", text)).strip()
        text = re.sub(r"[📣🤖🔗🆔]+\s*$", "", text).strip()
        text = re.sub(r"[-–—=]{3,}", " ", text).strip()
        if len(text) < 15:
            dropped += 1
            continue
        if text not in kept:
            kept.append(text)
    return kept, dropped


OPINION_MARKERS = (
    "راحت", "سخت", "نمره", "حضور", "غیاب", "امتحان", "میان‌ترم", "میانترم", "پایان‌ترم",
    "جزوه", "تدریس", "اکی", "اوکی", "عالی", "خوب", "بد ", "افتضاح", "پاس", "تشریحی",
    "تست", "پیشنهاد", "تعریف", "گیر", "سختگیر", "منصف", "واقعا", "بنظرم", "به نظر",
    "تجربه", "داشتم", "برداشتم", "ارائه", "حذف", "اضافه", "نمره‌دهی", "تصحیح",
)
QUESTION_MARKERS = ("؟", "?", "چجور", "چطور", "کسی", "چیه", "میدونه", "می‌دونه", "داره")


def prioritize_comments(comments: list[str]) -> list[str]:
    """نظرات حاوی ارزیابی واقعی را بالا می‌آورد؛ سوال‌های خالی را پایین."""
    def score(text: str) -> int:
        t = text.lower()
        pts = sum(2 for m in OPINION_MARKERS if m in t)
        if any(qm in t for qm in QUESTION_MARKERS):
            pts -= 3
        if len(t) > 40:
            pts += 1
        return pts

    return sorted(comments, key=score, reverse=True)


@dataclass
class DataStore:
    base_dir: str = "."
    courses: pd.DataFrame | None = None
    professors: list[Professor] = field(default_factory=list)
    curriculum: str = ""
    knowledge: str = ""
    log: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._load_courses()
        self._load_professors()
        self._load_curriculum()
        self._load_knowledge()
        self._parse_rules()

    # ---------- فایل‌ها

    def _path(self, name: str) -> str:
        return os.path.join(self.base_dir, name)

    def _load_courses(self) -> None:
        try:
            df = pd.read_excel(self._path("courses.xlsx"))
            df = df.fillna("")
            self.courses = df
            self.log.append(f"✅ جدول دروس: {len(df)} ردیف بارگذاری شد.")
        except Exception as exc:  # noqa: BLE001
            self.courses = None
            self.log.append(f"⚠️ خطا در خواندن courses.xlsx: {exc}")

    def _load_professors(self) -> None:
        try:
            with open(self._path("professors.txt"), encoding="utf-8") as f:
                raw = f.read()
        except OSError as exc:
            self.log.append(f"⚠️ خطا در خواندن professors.txt: {exc}")
            return

        header = re.compile(r"^===\s*شناسنامه استاد:\s*(.+?)\s*===\s*$", re.MULTILINE)
        hits = list(header.finditer(raw))
        blocks: list[tuple[str, str]] = []
        if hits:
            for i, m in enumerate(hits):
                end = hits[i + 1].start() if i + 1 < len(hits) else len(raw)
                body = raw[m.end():end]
                body = re.sub(r"^=+\s*$", "", body, flags=re.MULTILINE)
                body = re.sub(r"^تعداد نظرات:.*$", "", body, flags=re.MULTILINE)
                body = re.sub(r"\n{2,}", "\n", body).strip()
                if body:
                    blocks.append((m.group(1).strip(), body))
        else:
            # سازگاری با فایل‌های قدیمی که با --- جدا شده‌اند
            blocks = [(f"بلوک {i + 1}", b.strip())
                      for i, b in enumerate(raw.split("\n---\n")) if b.strip()]

        self.professors = []
        total_dropped = 0
        for name, body in blocks:
            comments, dropped = clean_comments(body)
            total_dropped += dropped
            clean_body = "\n".join(comments) if comments else "نظر مفیدی ثبت نشده است."
            self.professors.append(
                Professor(
                    name=name,
                    norm_name=normalize(name),
                    body=clean_body,
                    norm_body=normalize(clean_body),
                    comments=comments,
                    dropped_comments=dropped,
                )
            )
        self.log.append(
            f"✅ {len(self.professors)} شناسنامه‌ی استاد بارگذاری شد "
            f"({total_dropped} پیام لینکی/تکراری حذف شد)."
        )

    def _load_curriculum(self) -> None:
        try:
            reader = PdfReader(self._path("curriculum.pdf"))
            self.curriculum = "\n".join(
                (page.extract_text() or "") for page in reader.pages
            ).strip()
            self.log.append(f"✅ چارت درسی: {len(self.curriculum)} کاراکتر.")
        except Exception as exc:  # noqa: BLE001
            self.curriculum = ""
            self.log.append(f"⚠️ خطا در خواندن curriculum.pdf: {exc}")

    def _load_knowledge(self) -> None:
        try:
            with open(self._path("knowledge_base.txt"), encoding="utf-8") as f:
                self.knowledge = f.read().strip()
            self.log.append(f"✅ قوانین ورودی‌ها: {len(self.knowledge)} کاراکتر.")
        except OSError as exc:
            self.knowledge = ""
            self.log.append(f"⚠️ خطا در خواندن knowledge_base.txt: {exc}")

    # ---------- انتخاب بخش‌های مرتبط

    def _top_professors(self, kws: list[str], limit: int) -> tuple[list[Professor], bool]:
        """مرتبط‌ترین شناسنامه‌ها و این‌که آیا نام استاد صریحاً در سوال آمده یا نه."""
        if not kws or not self.professors:
            return [], False
        scored: list[tuple[int, int, Professor]] = []
        for prof in self.professors:
            name_score = 0
            body_score = 0
            for kw in kws:
                if kw in prof.norm_name:
                    name_score += 12
                hits = prof.norm_body.count(kw)
                if hits:
                    body_score += min(hits, 6)
            if name_score or body_score:
                scored.append((name_score, body_score, prof))
        if not scored:
            return [], False

        # اگر سوال مستقیماً اسم استاد(هایی) را آورده، فقط همان‌ها (به‌علاوه‌ی
        # حداکثر یک مورد از تطابق متنی قوی) آورده شود تا نویز کم شود.
        named = sorted((s for s in scored if s[0] > 0), key=lambda x: x[0], reverse=True)
        if named:
            best_name = named[0][0]
            named = [s for s in named if s[0] >= max(12, best_name * 0.6)]
            # بلوک‌هایی که فقط «در ضمن» اسم استاد را دارند (مثل فهرست لینک) حذف می‌شوند
            return [p for _, _, p in named[:limit]], True

        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0][1]
        keep = [s for s in scored if s[1] >= max(2, best * 0.35)]
        return [p for _, _, p in keep[:limit]], False

    def _course_match_score(self, row: pd.Series, kws: list[str]) -> int:
        haystack = normalize(f"{row.get('نام درس', '')} {row.get('استاد', '')}")
        score = 0
        for kw in kws:
            if kw in haystack:
                score += 3 if len(kw) >= 4 else 2
        return score

    def _top_courses(self, kws: list[str], limit: int) -> list[pd.Series]:
        if self.courses is None or not kws:
            return []
        scored = []
        for _, row in self.courses.iterrows():
            score = self._course_match_score(row, kws)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in scored[:limit]]

    # ---------- بررسی قطعی مجاز بودن درس (بدون اتکا به مدل)

    def _parse_rules(self) -> None:
        """نقشه‌ی «نام درس ← سال‌هایی که درس فقط برای آن‌ها مجاز است»."""
        self.entry_rules: dict[str, set[str]] = {}
        if not self.knowledge:
            return
        current_year: str | None = None
        for raw in self.knowledge.splitlines():
            line = raw.strip()
            if not line:
                continue
            m = re.match(r"^دروس ویژه دانشجویان ورودی\s*([0-9]{4})", normalize(line))
            if m:
                current_year = m.group(1)
                continue
            if line.startswith("دروسی که") or "قابل اخذ هستند" in line:
                current_year = None
                continue
            if current_year and " - " in line:
                course = normalize(line.split(" - ")[0])
                if course:
                    self.entry_rules.setdefault(course, set()).add(current_year)

    @staticmethod
    def _needs_knowledge(query: str) -> bool:
        nq = normalize(query)
        if re.search(r"\b140[0-9]\b", nq):
            return True
        return any(w in nq for w in ("ورودی", "مجاز", "محدودیت", "ظرفیت", "قابل اخذ", "پیش نیاز"))

    def check_eligibility(self, query: str) -> str:
        """اگر سوال «آیا درس X برای ورودی Y مجاز است؟» باشد، پاسخ قطعی را برمی‌گرداند."""
        nquery = normalize(query)
        years = {y for y in re.findall(r"\b(140[0-9])\b", nquery)}
        if not years:
            return ""

        # پیدا کردن نام درس: بلندترین تطابق از میان دروس ارائه‌شده و دروس قانون‌دار
        candidates: set[str] = set(self.entry_rules)
        if self.courses is not None:
            candidates |= {normalize(n) for n in self.courses.get("نام درس", []) if str(n).strip()}
        best = ""
        for cand in candidates:
            if len(cand) > 3 and cand in nquery and len(cand) > len(best):
                best = cand
        if not best:
            return ""

        year = sorted(years)[0]
        restricted_to = self.entry_rules.get(best)
        if restricted_to and year in restricted_to:
            verdict = f"مجاز است (این درس ویژه‌ی ورودی {year} است)."
        elif restricted_to:
            others = "، ".join(sorted(restricted_to))
            verdict = f"مجاز نیست (این درس فقط برای ورودی {others} مجاز است)."
        else:
            verdict = "مجاز است (این درس در فهرست دروس محدودشده نیست و برای همه‌ی ورودی‌ها قابل اخذ است)."
        return f"سوال: آیا «{best}» برای ورودی {year} مجاز است؟ ← {verdict}"

    def _curriculum_snippet(self, kws: list[str]) -> str:
        if not self.curriculum or not kws:
            return ""
        lines = []
        for line in self.curriculum.splitlines():
            nline = normalize(line)
            if nline and any(kw in nline for kw in kws):
                lines.append(line.strip())
        snippet = "\n".join(lines)
        return snippet[:MAX_CURRICULUM_CHARS]

    # ---------- API عمومی (برای fallback بدون مدل)

    @staticmethod
    def normalize(text: str) -> str:
        return normalize(text)

    @staticmethod
    def keywords(text: str) -> list[str]:
        return keywords(text)

    def match_professors(self, kws: list[str]) -> list[tuple[Professor, bool]]:
        profs, named = self._top_professors(kws, MAX_PROFESSOR_BLOCKS)
        return [(p, named) for p in profs]

    def match_courses(self, kws: list[str]) -> list[pd.Series]:
        return self._top_courses(kws, MAX_COURSE_ROWS)

    @staticmethod
    def format_course_row(row: pd.Series) -> str:
        return DataStore._format_course(row)

    def courses_for_professor(self, name: str) -> list[str]:
        """درس‌های این ترم که این استاد ارائه می‌دهد (برای پاسخ بدون مدل)."""
        if self.courses is None:
            return []
        target = normalize(name)
        rows = self.courses[
            self.courses.get("استاد", "").astype(str).map(normalize) == target
        ]
        if rows.empty:
            # تطابق نسبی (مثلاً بخشی از نام)
            rows = self.courses[
                self.courses.get("استاد", "").astype(str).map(
                    lambda v: target in normalize(v) or normalize(v) in target
                )
            ]
        return [self._format_course(r).lstrip("- ") for _, r in rows.head(6).iterrows()]

    # ---------- قالب‌بندی

    @staticmethod
    def _format_course(row: pd.Series) -> str:
        cells = [
            str(row.get("نام درس", "")).strip(),
            f"استاد: {str(row.get('استاد', '')).strip()}",
            str(row.get("زمان‌بندی تشکیل کلاس", "")).strip(),
            f"ورودی مجاز: {str(row.get('ورودی مجاز به اخذ', '')).strip()}",
            f"پیش‌نیاز: {str(row.get('پیشنیاز درس', '')).strip()}",
            f"ظرفیت: {str(row.get('حداکثر ظرفیت', '')).strip()}",
        ]
        return "- " + " | ".join(c for c in cells if c and not c.endswith(": "))

    def _course_index(self) -> str:
        if self.courses is None:
            return ""
        names = []
        for name in self.courses.get("نام درس", []):
            name = str(name).strip()
            if name and name not in names:
                names.append(name)
        return "، ".join(names)[:MAX_COURSE_INDEX_CHARS]

    # ---------- API عمومی

    def build_context(self, query: str) -> tuple[str, dict]:
        """متن زمینه‌ی متناسب با سوال کاربر + آمار مصرف را برمی‌گرداند."""
        kws = keywords(query)
        prof_limit = MAX_PROFESSOR_BLOCKS
        course_limit = MAX_COURSE_ROWS

        profs, prof_named = self._top_professors(kws, prof_limit)
        courses = self._top_courses(kws, course_limit)
        # اگر سوال درباره‌ی «مجاز بودن/زمان درس» است و اسم استادی نیامده،
        # نظرات استادان فقط بودجه‌ی زمینه را می‌خورد؛ حذفشان می‌کنیم.
        if profs and not prof_named and courses:
            profs = []
        curriculum = self._curriculum_snippet(kws)

        sections: list[tuple[str, str]] = []

        # قوانین ورودی‌ها فقط وقتی مربوط است که سوال درباره‌ی مجاز بودن/ورودی باشد؛
        # در سوال «استادشناسی» فقط نویز و مصرف توکن است.
        if self.knowledge and self._needs_knowledge(query):
            sections.append(("قوانین ورودی‌ها و مجاز بودن دروس", self.knowledge))

        verdict = self.check_eligibility(query)
        if verdict:
            sections.insert(0, ("پاسخ قطعی بررسی خودکار (این خط درست است، از آن استفاده کن)", verdict))

        if courses:
            rows = "\n".join(self._format_course(r) for r in courses)
            sections.append(("دروس مرتبط با سوال (از جدول ارائه دروس این ترم)", rows))
        else:
            index = self._course_index()
            if index:
                sections.append(("فهرست دروس ارائه‌شده این ترم", index))

        if profs:
            blocks = []
            for p in profs:
                ordered = prioritize_comments(p.comments) or [p.body]
                body = "\n".join(ordered)
                if len(body) > MAX_PROF_BLOCK_CHARS:
                    body = body[:MAX_PROF_BLOCK_CHARS].rstrip() + " ..."
                note = ""
                if not p.comments:
                    note = ("\n(در آرشیو فقط سوال/لینک درباره‌ی این استاد بوده و "
                            "ارزیابی واقعی دانشجویی ثبت نشده است.)")
                blocks.append(
                    f"«{p.name}» (تعداد نظر مفید: {len(p.comments)}):\n{body}{note}"
                )
            sections.append(("نظرات دانشجویان درباره استاد(های) سوال", "\n\n".join(blocks)))

        if curriculum:
            sections.append(("بخش مرتبط از چارت درسی", curriculum))

        # --- رعایت بودجه: اولویت حذف از کم‌اهمیت‌ترین بخش
        def render(secs: list[tuple[str, str]]) -> str:
            return "\n\n".join(f"### {title}\n{body}" for title, body in secs)

        while len(render(sections)) > MAX_CONTEXT_CHARS and sections:
            titles = [t for t, _ in sections]
            if "بخش مرتبط از چارت درسی" in titles:
                sections.pop(titles.index("بخش مرتبط از چارت درسی"))
            elif len(sections) and titles[-1] not in ("قوانین ورودی‌ها و مجاز بودن دروس",):
                sections.pop()
            else:
                break

        context = render(sections)
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n... (بریده شد)"

        stats = {
            "verdict": verdict,
            "keywords": kws,
            "professors": {p.name: len(p.comments) for p in profs},
            "courses": len(courses),
            "has_curriculum": bool(curriculum),
            "chars": len(context),
            "tokens": estimate_tokens(context),
        }
        return context, stats


if __name__ == "__main__":  # اجرای مستقیم برای بررسی سریع اندازه‌ی زمینه
    store = DataStore(".")
    for line in store.log:
        print(line)
    for q in ["بهینه سازی خطی برای ورودی ۱۴۰۳ مجازه؟", "استاد ایزدیخواه چطوره؟",
              "ساختمان داده و الگوریتم ها با همامی", "سلام"]:
        ctx, st = store.build_context(q)
        print(f"\n--- سوال: {q}\n    {st['chars']} کاراکتر / ~{st['tokens']} توکن | "
              f"استادها: {st['professors']} | درس‌ها: {st['courses']}")
