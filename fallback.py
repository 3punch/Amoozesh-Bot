"""
موتور پاسخ‌دهی ربات (بدون مدل).

هدف این ماژول «گزارش خام» نیست؛ ربات باید **نتیجه‌ی خودش** را بگوید:
یک جمع‌بندی کوتاه و قابل‌عمل از داده‌های پروژه، بدون کپی‌کردن پیام‌های
دانشجویان و بدون تولید متن آزاد.

منابع داده (همه در مخزن):
    courses.xlsx        جدول ارائه دروس این ترم
    professors.txt      ارزیابی‌های دانشجویان (فرم استادشناسی + نظرات)
    knowledge_base.txt  محدودیت ورودی‌ها

قواعد طراحی:
  ۱. هیچ جمله‌ای از آرشیو عیناً نقل نمی‌شود؛ فقط نتیجه‌ی استخراج‌شده گزارش می‌شود.
  ۲. هر ادعا باید به داده‌ی قابل مشاهده متصل باشد (امتیاز فرم، متن فرم،
     یا شمارش روشن نظرات هم‌جهت).
  ۳. اگر شواهد کافی نبود، صریح گفته می‌شود «ارزیابی ثبت نشده است».
"""

from __future__ import annotations

import re

from retrieval import (
    OPINION_MARKERS,
    QUESTION_MARKERS,
    normalize,
    prioritize_comments,
)

# ---------------------------------------------------------------- داده‌های فرم

FORM_ITEM = {
    "تدریس": r"پیوستگی[^:]*:\s*(\d+)",
    "تسلط": r"(?:دانش عمومی و تسلط|دانش عمومی)[^:]*:\s*(\d+)",
    "انتقال مطالب": r"توانایی انتقال مطالب[^:]*:\s*(\d+)",
    "مدیریت کلاس": r"مدیریت کلاس[^:]*:\s*(\d+)",
    "پاسخ‌گویی": r"پاسخگویی[^:]*:\s*(\d+)",
    "رفتار": r"آداب و رفتار اجتماعی[^:]*:\s*(\d+)",
}

# برچسب فیلدها در فرم‌های استادشناسی یکدست نیست؛ با «توقف روی فیلد بعدی» می‌خوانیم
FIELD_STOPS = (
    "منابع", "وضعیت نمره", "ارزیابی", "توضیح", "راه ارتباطی", "راه های ارتباطی",
    "ترمی که", "چه ترمی", "اهمیت حضور", "نام دروس", "گروه درسی",
    "☆", "📚", "📖", "📝", "✅", "⭐", "📄", "📲", "♻️", "⚠️", "🎓",
)
SEPARATORS = " \t:؛،.؟┘●┅┄☆⁉️📚📖📝✅⭐📄📲♻️⚠️🖐💠🏫🎓"


def _field(form: str | None, start_re: str, limit: int = 90) -> str:
    """مقدار یک فیلد فرم را تا شروع فیلد بعدی برمی‌گرداند."""
    if not form:
        return ""
    match = re.search(start_re, form)
    if not match:
        return ""
    rest = form[match.end():]
    # «پاسخ :» و جداکننده‌های تزئینی پیش از مقدار واقعی می‌آیند
    for _ in range(3):
        rest = re.sub(rf"^[{SEPARATORS}]+", "", rest)
        rest = re.sub(r"^پاسخ\s*:\s*", "", rest)
    cut = len(rest)
    for stop in FIELD_STOPS:
        index = rest.find(stop)
        if 0 <= index < cut:
            cut = index
    value = rest[:min(cut, limit)]
    value = re.sub(rf"^[{SEPARATORS}]+", "", value)
    return re.sub(r"\s+", " ", value).strip(" :،؛-")


FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
TO_ASCII = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# ---------------------------------------------------------------- ابزار متن


def _fa(value) -> str:
    return str(value).translate(FA)


def _cell(value) -> str:
    """مقدار یک خانه‌ی جدول، آماده برای نمایش (بدون nan، با ارقام فارسی)."""
    text = "" if value is None else str(value).strip()
    if text.lower() in ("nan", "none", "-"):
        return ""
    text = re.sub(r"\s+", " ", text.replace("\u200c", " "))
    text = text.replace("ي", "ی").replace("ك", "ک")
    return text.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .،:؛-")


# ---------------------------------------------------------------- برنامه‌ی هفتگی

_DAY_RE = re.compile(
    r"(یکشنبه|سه\s*شنبه|چهارشنبه|پنجشنبه|دوشنبه|شنبه|جمعه)"
    r"\s*از\s*(\d{1,2}:\d{2})\s*تا\s*(\d{1,2}:\d{2})"
)


def format_schedule(raw) -> str:
    """«دوشنبه از 11:20 تا 12:10 و دوشنبه از 12:40 تا 13:30» → «دوشنبه ۱۱:۲۰–۱۲:۱۰ و ۱۲:۴۰–۱۳:۳۰»"""
    text = _cell(raw)
    if not text:
        return ""
    text = (
        text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
        .translate(TO_ASCII)
    )
    text = re.sub(r"\s+", " ", text)
    days: list[str] = []
    slots: dict[str, list[str]] = {}
    for day, start, end in _DAY_RE.findall(text):
        day = re.sub(r"\s+", " ", day)
        if day not in slots:
            slots[day] = []
            days.append(day)
        slots[day].append(f"{_fa(start)}–{_fa(end)}")
    if not days:
        return ""
    return "؛ ".join(f"{day} {' و '.join(slots[day])}" for day in days)


def entry_label(raw) -> str:
    """«ورودی مجاز به اخذ» → عبارت خوانا برای دانشجو."""
    text = _cell(raw)
    if not text:
        return ""
    norm = normalize(text)
    if "تمامی" in norm or "همه" in norm:
        return "همه‌ی ورودی‌ها"
    match = re.search(r"(\d{4})", text.translate(TO_ASCII))
    if match:
        return f"فقط ورودی {_fa(match.group(1))}"
    return norm


def course_line(row, with_professor: bool = True) -> str:
    """یک ردیف جدول را به جمله‌ی خوانا تبدیل می‌کند."""
    name = _cell(row.get("نام درس"))
    professor = _cell(row.get("استاد")) if with_professor else ""
    schedule = format_schedule(row.get("زمان‌بندی تشکیل کلاس"))

    head = " — ".join(part for part in (name, professor) if part)
    details = [schedule or "زمان اعلام نشده"]
    prereq = _cell(row.get("پیشنیاز درس"))
    if prereq:
        details.append(f"پیش‌نیاز: {prereq}")
    capacity = _cell(row.get("حداکثر ظرفیت"))
    if capacity:
        details.append(f"ظرفیت {_fa(capacity)}")
    entry = entry_label(row.get("ورودی مجاز به اخذ"))
    if entry:
        details.append(entry)
    return f"• {head} · " + " · ".join(details)


# ---------------------------------------------------------------- تحلیل نظرات

POSITIVE = (
    "خوب", "عالی", "راحت", "ارفاق", "منصف", "مسلط", "روان", "پیشنهاد",
    "اکی", "اوکی", "راضی", "محترم", "احترام", "بهتر", "کافی", "تمیز",
)
NEGATIVE = (
    "بد", "افتضاح", "سختگیر", "ضعیف", "ناراضی", "پشیمون", "خشک",
    "بدترین", "نامفهوم", "مشکل", "نمیده", "نمره کم", "سخت",
)
THEMES = {
    "نمره‌دهی": ("نمره", "ارفاق", "تصحیح", "نمره‌دهی"),
    "حضور و غیاب": ("حضور", "غیاب"),
    "امتحان و منابع": ("امتحان", "سوال", "منابع", "جزوه"),
    "برخورد و پاسخ‌گویی": ("اخلاق", "برخورد", "احترام", "پاسخگو"),
    "کیفیت تدریس": ("تدریس", "توضیح", "انتقال"),
}
THEME_POSITIVE = {
    "نمره‌دهی": "نمره‌دهی با ارفاق و دست باز",
    "حضور و غیاب": "روی حضور و غیاب سختگیر نیست",
    "امتحان و منابع": "منابع و امتحان معقول توصیف شده",
    "برخورد و پاسخ‌گویی": "برخورد محترمانه و پاسخگو",
    "کیفیت تدریس": "تدریس روان و قابل فهم",
}
THEME_NEGATIVE = {
    "نمره‌دهی": "نمره‌دهی سختگیرانه",
    "حضور و غیاب": "حضور و غیاب برایش مهم و اجباری است",
    "امتحان و منابع": "امتحان و منابع سنگین",
    "برخورد و پاسخ‌گویی": "برخورد ضعیف گزارش شده",
    "کیفیت تدریس": "انتقال مطالب ضعیف گزارش شده",
}


def _is_question(text: str) -> bool:
    return any(marker in text for marker in QUESTION_MARKERS)


def _form(comments: list[str]) -> str | None:
    """کامل‌ترین فرم استادشناسی موجود در نظرات."""
    forms = [c for c in comments if "پیوستگی و یکپارچگی تدریس" in c]
    return max(forms, key=len) if forms else None


def _scores(form: str | None) -> dict[str, int]:
    if not form:
        return {}
    out: dict[str, int] = {}
    for label, pattern in FORM_ITEM.items():
        match = re.search(pattern, form)
        if match:
            out[label] = int(match.group(1))
    return out


GRADING_RE = r"وضعیت نمره\s*دادن[^:]*:"
ATTENDANCE_RE = r"اهمیت حضور و غیاب|حضور و غیاب\s*[:┘\s]"
RESOURCES_RE = r"منابع معرفی شده برای امتحان کافی است\??\s*[:┘\s]*"


def _normalize_form_value(value: str) -> str:
    value = re.sub(r"^پاسخ\s*:", "", value)
    return re.sub(r"\s+", " ", value).strip(" :،؛-")


def _form_text(form: str | None, key: str) -> str:
    patterns = {"نمره‌دهی": GRADING_RE, "حضور": ATTENDANCE_RE, "منابع": RESOURCES_RE}
    return _normalize_form_value(_field(form, patterns[key]))


def _polarity(comments: list[str]) -> dict[str, tuple[int, int]]:
    """برای هر موضوع: (تعداد نظر هم‌جهت مثبت، تعداد نظر هم‌جهت منفی)"""
    out = {theme: [0, 0] for theme in THEMES}
    for comment in comments:
        if _is_question(comment):
            continue
        pos = sum(comment.count(word) for word in POSITIVE)
        neg = sum(comment.count(word) for word in NEGATIVE)
        if pos == neg:
            continue
        for theme, words in THEMES.items():
            if any(word in comment for word in words):
                out[theme][0 if pos > neg else 1] += 1
    return {theme: (pos, neg) for theme, (pos, neg) in out.items()}


def _verdict(scores: dict[str, int], polarity: dict[str, tuple[int, int]],
             evidence: int) -> str:
    if scores:
        average = sum(scores.values()) / len(scores)
        if average >= 8.5:
            return "استاد خوبی است؛ ارزیابی دانشجویان مثبت و یکدست است."
        if average >= 7:
            return "ارزیابی کلی مثبت است، ولی در برخی شاخص‌ها ضعف دارد."
        if average >= 5.5:
            return "ارزیابی متوسط است؛ نظرات دانشجویان هم‌جهت نیست."
        return "ارزیابی دانشجویان ضعیف است؛ با احتیاط انتخاب کن."

    positive = sum(pos for pos, neg in polarity.values() if pos > neg)
    negative = sum(neg for pos, neg in polarity.values() if neg > pos)
    if positive >= negative + 2:
        return "نظرهای ثبت‌شده بیشتر مثبت است."
    if negative >= positive + 2:
        return "نظرهای ثبت‌شده بیشتر منفی است؛ با احتیاط انتخاب کن."
    if evidence == 0:
        return "ارزیابی ثبت‌شده‌ای برای این استاد در آرشیو نیست."
    return "نظرات درباره‌ی این استاد متناقض است و جمع‌بندی قطعی ممکن نیست."


# ---------------------------------------------------------------- پاسخ‌ها


def professor_answer(store, name: str, course: str = "") -> str | None:
    """نتیجه‌گیری ربات درباره‌ی یک استاد (بدون نقل‌قول از پیام‌ها)."""
    professor = next(
        (p for p in store.professors if p.norm_name == normalize(name)), None
    )
    if professor is None:
        return None

    comments = professor.comments
    form = _form(comments)
    scores = _scores(form)
    polarity = _polarity(comments)
    evidence = sum(1 for c in comments if not _is_question(c) and
                   any(marker in c for marker in OPINION_MARKERS))

    lines = [
        f"👤 {professor.name} · بر پایه‌ی {_fa(len(comments))} پیام آرشیو",
        f"🎯 نتیجه: {_verdict(scores, polarity, evidence)}",
    ]

    if scores:
        average = sum(scores.values()) / len(scores)
        lines.append(f"📊 ارزیابی دانشجویان: {_fa(f'{average:.1f}')} از ۱۰")
        lines.append("   " + " · ".join(f"{k} {_fa(v)}" for k, v in scores.items()))

    strengths: list[str] = []
    warnings: list[str] = []

    grading = _form_text(form, "نمره‌دهی")
    if grading:
        if any(word in grading for word in ("ارفاق", "دست باز", "خوب")):
            strengths.append(f"نمره‌دهی: {grading}")
        elif any(word in grading for word in ("سخت", "کم", "بد")):
            warnings.append(f"نمره‌دهی: {grading}")

    attendance = _form_text(form, "حضور")
    if attendance:
        if any(word in attendance for word in ("نمی", "مهم نیست", "سختگیر نیست", "حساس نیست")):
            strengths.append("روی حضور و غیاب سختگیر نیست")
        else:
            warnings.append("حضور و غیاب برگزار می‌شود و برایش مهم است")

    resources = _form_text(form, "منابع")
    if resources:
        if resources.startswith("بله"):
            strengths.append("منابع معرفی‌شده برای امتحان کافی است")
        elif resources.startswith("خیر"):
            warnings.append("منابع کلاس برای امتحان کافی نیست")
        elif "تاحدودی" in resources or "تا حدی" in resources:
            warnings.append("کفایت منابع برای امتحان: تا حدی")

    for theme, (pos, neg) in polarity.items():
        if pos - neg >= 2:
            strengths.append(THEME_POSITIVE[theme])
        elif neg - pos >= 2:
            warnings.append(THEME_NEGATIVE[theme])

    def unique(items: list[str]) -> list[str]:
        seen: list[str] = []
        for item in items:
            if item not in seen:
                seen.append(item)
        return seen[:4]

    strengths, warnings = unique(strengths), unique(warnings)
    # یک نکته ممکن است در دو دسته بیاید؛ تکراری‌ها حذف می‌شوند
    warnings = [item for item in warnings if item not in strengths]

    notes: list[str] = []
    if not strengths and not warnings and evidence and not course:
        notes.append("ارزیابی‌های موجود پراکنده است و جمع‌بندی روشن نمی‌دهد؛ "
                     "برای تصمیم بهتر نام درس را هم بپرس.")
    if not scores and not evidence:
        notes.append("در آرشیو ارزیابی روشنی درباره‌ی این استاد ثبت نشده است.")

    if strengths:
        lines.append("")
        lines.append("✅ نقاط قوت")
        lines.extend(f"• {item}" for item in strengths)
    if warnings:
        lines.append("")
        lines.append("⚠️ نکات مهم")
        lines.extend(f"• {item}" for item in warnings)
    if notes:
        lines.append("")
        lines.extend(f"ℹ️ {item}" for item in notes)

    courses = courses_for_professor(store, professor.name, course_norm=course)
    if courses:
        lines.append("")
        lines.append(f"📚 ارائه‌های این استاد در «{_cell(course)}»" if course
                     else "📚 ارائه‌ی این ترم")
        lines.extend(courses)

    return "\n".join(lines)


def courses_for_professor(store, name: str, limit: int = 6,
                          course_norm: str = "") -> list[str]:
    """درس‌های این ترم یک استاد؛ با course_norm فقط همان درس."""
    if store.courses is None:
        return []
    target = normalize(name)
    matches = []
    for _, row in store.courses.iterrows():
        professor = normalize(_cell(row.get("استاد")))
        if not (professor == target or
                (professor and (target in professor or professor in target))):
            continue
        if course_norm:
            row_course = normalize(_cell(row.get("نام درس")))
            if row_course != course_norm and course_norm not in row_course:
                continue
        matches.append(row)
    lines: list[str] = []
    for row in matches[:limit]:
        schedule = format_schedule(row.get("زمان‌بندی تشکیل کلاس"))
        name_ = _cell(row.get("نام درس")) or "درس"
        details = [schedule or "زمان اعلام نشده"]
        capacity = _cell(row.get("حداکثر ظرفیت"))
        if capacity:
            details.append(f"ظرفیت {_fa(capacity)}")
        entry = entry_label(row.get("ورودی مجاز به اخذ"))
        if entry:
            details.append(entry)
        lines.append(f"• {name_} — " + " · ".join(details))
    return lines


def eligibility_answer(store, info: dict) -> str:
    """نتیجه‌ی قطعی مجاز بودن یک درس برای یک ورودی."""
    verdict = "مجاز است ✅" if info["allowed"] else "مجاز نیست ❌"
    lines = [f"🎯 نتیجه: «{info['course']}» برای ورودی {_fa(info['year'])} {verdict}",
             info["reason"]]

    allowed_rows = info.get("allowed_rows") or []
    blocked_rows = info.get("blocked_rows") or []
    if allowed_rows and blocked_rows:
        lines.append("")
        lines.append("✅ ارائه‌های باز برای این ورودی")
        lines.extend(course_line(row) for row in allowed_rows[:3])
        lines.append("")
        lines.append("⛔ ارائه‌هایی که برای این ورودی باز نیستند")
        lines.extend(course_line(row) for row in blocked_rows[:3])
    elif allowed_rows:
        lines.append("")
        lines.append("📚 این ترم چطور ارائه می‌شود")
        lines.extend(course_line(row) for row in allowed_rows[:4])
    elif blocked_rows:
        explicit = [row for row in blocked_rows if store._row_years(row)]
        lines.append("")
        lines.append("⛔ ارائه‌هایی که برای این ورودی باز نیستند")
        lines.extend(course_line(row) for row in (explicit or blocked_rows)[:4])

    if not (allowed_rows or blocked_rows):
        rows = store.rows_for_course(info["course"])
        if rows:
            lines.append("")
            lines.append("📚 این ترم چطور ارائه می‌شود")
            lines.extend(course_line(row) for row in rows[:4])
    return "\n".join(lines)


def courses_answer(store, rows: list, query: str = "") -> str:
    """فهرست ارائه‌های یک درس (یا چند درس مرتبط)."""
    if not rows:
        return ""
    main_name = _cell(rows[0].get("نام درس")) or "دروس پیدا‌شده"
    same = [r for r in rows if _cell(r.get("نام درس")) == main_name]
    others = [r for r in rows if _cell(r.get("نام درس")) != main_name]

    count = len(same)
    lines = [f"🎯 نتیجه: {_fa(count)} ارائه برای «{main_name}» در این ترم ثبت شده است."]
    lines.append("")
    lines.extend(course_line(row) for row in same[:5])
    query_tokens = set(normalize(query).split()) if query else set()

    def related(name: str) -> bool:
        if not query_tokens:
            return False
        name_tokens = set(normalize(name).split())
        return len(query_tokens & name_tokens) >= 2

    if others:
        other_names = []
        for row in others:
            name = _cell(row.get("نام درس"))
            if name and name not in other_names and related(name):
                other_names.append(name)
        if other_names:
            lines.append("")
            lines.append("🔎 موارد مرتبط دیگر: " + "، ".join(other_names[:3]))
    return "\n".join(lines)


def not_found_answer(store, query: str) -> str:
    """وقتی چیزی در داده پیدا نشد: همان را صریح می‌گوید و راهنمایی می‌دهد."""
    tried = _fa(re.sub(r"\s+", " ", query.strip()))[:60]
    lines = [f"🎯 نتیجه: در داده‌ی این ترم چیزی برای «{tried}» پیدا نکردم."]
    if store.courses is not None and len(store.courses):
        lines.append(f"ℹ️ داده‌ی فعلی شامل {_fa(len(store.courses))} ردیف ارائه‌ی درس "
                     f"و {_fa(len(store.professors))} شناسنامه‌ی استاد است؛ شاید نام "
                     "درس یا استاد کمی متفاوت نوشته شده باشد.")
    lines.append("")
    lines.append("می‌توانی این‌طور بپرسی:")
    lines.append("• استاد آذر ابوالقاسمی چطور است؟")
    lines.append("• آیا درس بهینه سازی خطی برای ورودی ۱۴۰۴ مجاز است؟")
    lines.append("• درس مبانی کارآفرینی چه زمانی ارائه شده؟")
    return "\n".join(lines)


def answer(store, query: str, want_model: bool = True) -> str | None:
    """پاسخ نهایی ربات برای یک پرسش، یا None اگر چیزی برای گفتن نبود."""
    info = store.eligibility_info(query)
    if info:
        return eligibility_answer(store, info)

    keywords = store.keywords(query)
    if not keywords:
        return None

    matches = store.match_professors(keywords)
    named = [professor.name for professor, is_named in matches if is_named]
    if named:
        # اگر نام درس هم در پرسش باشد، فقط ارائه‌های همان درس نمایش داده می‌شود
        course_norm = ""
        query_tokens = set(normalize(query).split())
        best_overlap = 0
        for row in store.match_courses(keywords):
            candidate = normalize(_cell(row.get("نام درس")))
            tokens = set(candidate.split())
            if not tokens:
                continue
            overlap = len(tokens & query_tokens)
            need = min(len(tokens), max(1, len(tokens) - 1))
            if overlap >= need and overlap > best_overlap:
                course_norm, best_overlap = candidate, overlap
        text = professor_answer(store, named[0], course=course_norm)
        if text:
            return text

    rows = store.match_courses(keywords)
    if rows:
        return courses_answer(store, rows, query)

    return not_found_answer(store, query)


# ---------------------------------------------------------------- پاکسازی مدل

BULLET_RE = re.compile(r"^[*\-•▪◦]\s+")


def _plain(line: str) -> str:
    """مارک‌داون مدل را به متن ساده‌ی تلگرام تبدیل می‌کند."""
    line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
    line = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", line)
    line = re.sub(r"`([^`]+)`", r"\1", line)
    line = re.sub(r"#{1,6}\s*", "", line)
    if BULLET_RE.match(line):
        line = BULLET_RE.sub("• ", line)
    return line.strip()


def sanitize_model_text(text: str, allow_verdict: bool = False) -> str:
    """خطوط پرخطر مدل را حذف می‌کند (حکم بی‌ربط، مارک‌داون، پرحرفی)."""
    if not text:
        return ""
    drop_markers = () if allow_verdict else ("نتیجه: مجاز است", "نتیجه: مجاز نیست")
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(marker in stripped for marker in drop_markers):
            continue
        lines.append(_plain(stripped))
    return "\n".join(lines).strip()[:900]


TIME_RE = re.compile(r"\d{1,2}:\d{2}")
NUM_RE = re.compile(r"\d+")


def verify_model_text(text: str, context: str) -> tuple[bool, str]:
    """
    آیا جمع‌بندی مدل با «اطلاعات» سازگار است؟

    همه‌ی ساعت‌ها و اعدادی که مدل می‌نویسد باید عیناً در زمینه باشند؛
    در غیر این صورت متن دور ریخته می‌شود (مدل‌های کوچک ساعت و ظرفیت می‌سازند).
    """
    if not text.strip():
        return False, "خالی"
    if "اطلاعات موجود نیست" in text:
        return False, "مدل گفت اطلاعاتی نیست (متناقض با داده)"

    def norm(value: str) -> str:
        return re.sub(r"[ \t\u200c]+", " ", value.translate(TO_ASCII))

    ctx = norm(context)
    ctx_times = set(TIME_RE.findall(ctx))
    ctx_nums = set(NUM_RE.findall(ctx))
    ctx_lines = [line for line in ctx.splitlines() if line.strip()]

    out = norm(text)

    made_up = [t for t in TIME_RE.findall(out) if t not in ctx_times]
    if made_up:
        return False, f"ساعت ساختگی: {', '.join(made_up[:3])}"

    for line in out.splitlines():
        times = TIME_RE.findall(line)
        if len(times) >= 2 and not any(all(t in ctx_line for t in times) for ctx_line in ctx_lines):
            return False, f"ترکیب ساعت اشتباه: {' و '.join(times[:3])}"

    novel = sorted({n for n in NUM_RE.findall(out) if n not in ctx_nums}, key=len, reverse=True)
    if novel:
        return False, f"عدد ساختگی: {', '.join(novel[:3])}"
    return True, "ok"


OFFLINE_NOTE = "\n\n_(مدل محلی در دسترس نبود؛ این پاسخ مستقیم از داده‌های پروژه ساخته شد.)_"

# سازگاری با نسخه‌های قبلی
professor_card = professor_answer
