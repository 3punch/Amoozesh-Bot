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

# واژه‌نامه‌ی قطبیت. متن آرشیو خودمانی و کنایه‌آمیز است، پس ترتیب مهم است:
# اول نفی‌ها و اصطلاحات («خوب نیست» مثبت نیست)، بعد واژه‌های عمومی.
QUESTION_WORDS = ("چجور", "چطور", "چیه", "کسی", "می‌دونه", "میدونه", "کدوم")


def _is_question(text: str) -> bool:
    """پرسش واقعی؛ پیام بلند با یک علامت سوال نمایشی، نظر حساب می‌شود."""
    norm = normalize(text)
    if any(word in norm for word in QUESTION_WORDS):
        return True
    if any(mark in text for mark in ("؟", "?")):
        return len(norm.split()) <= 8
    return False


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


SENTIMENT_RULES: tuple[tuple[str, int], ...] = (
    # --- منفی
    (r"خوب\s*(?:نیست|نیسن|نیس|نبود|نبوده|نباشه|نبودن)", -2),
    (r"تاس\s*(?:می\s*نداز|مینداز|انداز|انداخت|اندازی|بنداز)", -3),
    (r"رندوم", -2),
    (r"موجب\s*سلامتی", -3),
    (r"برندار", -3),
    (r"بی\s*سواد", -3),
    (r"بی\s*مسئولیت", -3),
    (r"وقت\s*تلف", -2),
    (r"نگاه\s*نمی", -2),
    (r"افتضاح|بدترین|فاجعه", -3),
    (r"سخت\s*گیر|سختگیر", -2),
    (r"نمره\s*کم", -2),
    (r"نامفهوم|نمی\s*فهم|نمیفهم|نفهمید", -1),
    (r"پشیمون", -2),
    (r"ضعیف", -2),
    (r"ناراضی", -2),
    (r"حذف\s*شد", -1),
    (r"سنگین", -1),
    (r"بی\s*خودی|الکی", -1),
    (r"جرقه\s*می\s*زن|جرقه\s*می\s*زنم", -1),
    # --- مثبت
    (r"ارفاق", +2),
    (r"منصف", +2),
    (r"عالی", +2),
    (r"سواد\s*خوب", +2),
    (r"درست\s*تر\s*نمره", +2),
    (r"(?:حال\s*می|حال\s*می\s*کردم|حالم\s*باهاش)", +1),
    (r"راحت", +1),
    (r"راضی", +1),
    (r"پیشنهاد\s*می", +1),
    (r"مسلط", +2),
    (r"روان", +1),
    (r"محترم|احترام", +1),
    (r"کافی(?:ه|ست| بود)?", +1),
    (r"یاد\s*می\s*دهد|یاد\s*میده|یاد\s*بگیر", +1),
    (r"خوب(?:ه|ی| است| بود| هست|ین)?", +2),
)
SENTIMENT_RULES = tuple((re.compile(rx), weight) for rx, weight in SENTIMENT_RULES)


def _sentiment(text: str) -> int:
    """امتیاز قطبیت یک پیام (منفی/صفر/مثبت).

    هر الگو پس از تطبیق از متن حذف می‌شود تا «خوب نیست» یک بار منفی شمرده
    شود، نه یک بار مثبت («خوب») و یک بار منفی.
    """
    norm = normalize(text)
    total = 0
    for rx, weight in SENTIMENT_RULES:
        norm, count = rx.subn(" ", norm)
        if count:
            total += weight
    return total


def _is_opinion(text: str) -> bool:
    """پیام واقعاً حرفی برای گفتن دارد یا فقط سوال/شوخی/هماهنگی است."""
    if _is_question(text):
        return False
    if _sentiment(text):
        return True
    norm = normalize(text)
    return len(norm.split()) >= 6 and any(marker in norm for marker in OPINION_MARKERS)


def _theme_polarity(entries: list[tuple[str, int]]) -> dict[str, tuple[int, int]]:
    """برای هر موضوع: (تعداد پیام هم‌جهت مثبت، تعداد پیام هم‌جهت منفی)."""
    out = {theme: [0, 0] for theme in THEMES}
    for comment, score in entries:
        if not score:
            continue
        norm = normalize(comment)
        for theme, words in THEMES.items():
            if any(normalize(word) in norm for word in words):
                out[theme][0 if score > 0 else 1] += 1
    return {theme: (pos, neg) for theme, (pos, neg) in out.items()}


def _polarity(comments: list[str]) -> dict[str, tuple[int, int]]:
    """نسخه‌ی ساده (بدون نسبت‌دادن به استاد) — برای سازگاری."""
    return _theme_polarity(
        [(c, _sentiment(c)) for c in comments if not _is_question(c)]
    )


def _verdict(scores: dict[str, int], positive: int, negative: int,
             evidence: int) -> str:
    """حکم کوتاه و قابل‌عمل از داده‌ی موجود."""
    if scores:
        average = sum(scores.values()) / len(scores)
        if average >= 8.5:
            return "استاد خوبی است؛ ارزیابی دانشجویان مثبت و یکدست است."
        if average >= 7:
            return "ارزیابی کلی مثبت است، ولی در برخی شاخص‌ها ضعف دارد."
        if average >= 5.5:
            return "ارزیابی متوسط است؛ نظرات دانشجویان هم‌جهت نیست."
        return "ارزیابی دانشجویان ضعیف است؛ با احتیاط انتخاب کن."

    if positive + negative == 0:
        if evidence:
            return "نظرات موجود بیشتر پرسش و شوخی است؛ ارزیابی روشنی ثبت نشده."
        return "ارزیابی ثبت‌شده‌ای برای این استاد در آرشیو نیست."

    ratio = positive / max(positive + negative, 1)
    if ratio >= 0.66:
        return "نظرهای ثبت‌شده بیشتر مثبت است."
    if ratio <= 0.34:
        return "نظرهای ثبت‌شده بیشتر منفی است؛ با احتیاط انتخاب کن."
    if negative > positive:
        return "انتقادها بیشتر از تعریف‌هاست، هرچند نظر مثبت هم ثبت شده."
    return "نظرات درباره‌ی این استاد متناقض است و جمع‌بندی قطعی ممکن نیست."


# ---------------------------------------------------------------- پاسخ‌ها


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


# بندهای یک پیام با این جداکننده‌ها شکسته می‌شود تا معلوم شود هر حرف درباره‌ی
# کدام استاد است («غلامیان درست تر نمره میده ولی تهرانیان تاس میندازه»).
CLAUSE_SPLIT = re.compile(r"[.!؟?؛،\n]+|\s(?:ولی|اما|پس|چون|وگرنه)\s")


def _name_keys(store) -> dict[str, str]:
    """نام خانوادگی یکتای هر استاد ← نام کامل.

    فقط واژه‌ی آخر نام (فامیل) نگه داشته می‌شود و آن هم وقتی در نام یک استاد
    یکتا باشد؛ وگرنه «محمد» یا «امید» (که واژه‌ی معمولی هم هستند) پیام‌های
    بی‌ربط را به استاد اشتباه می‌چسبانند.
    """
    surname: dict[str, list[str]] = {}
    for professor in store.professors:
        tokens = professor.norm_name.split()
        if not tokens:
            continue
        surname.setdefault(tokens[-1], []).append(professor.name)
    return {key: names[0] for key, names in surname.items()
            if len(names) == 1 and len(key) >= 3}


def _mentions(norm: str, key: str) -> int:
    """جای نام خانوادگی در متن (با پسوندهای چسبیده مثل «غلامیانه»)، یا -۱."""
    match = re.search(rf"(?<!\w){re.escape(key)}(?:م|ت|ش|ها|های|ه|ی|و|رو|هم|ست)?(?!\w)",
                      norm)
    return match.start() if match else -1


def _attributed(comment: str, keys: dict[str, str], default: str) -> dict[str, int]:
    """قطبیت پیام را به استاد صاحب هر بند نسبت می‌دهد.

    اگر بندی نام کسی را نیاورد، ادامه‌ی حرف همان استاد قبلی حساب می‌شود؛
    و اگر کل پیام بی‌نام باشد، به استاد همان شناسنامه (default) می‌رسد.
    """
    scores: dict[str, int] = {}
    current = default
    for clause in CLAUSE_SPLIT.split(comment):
        if not clause.strip():
            continue
        norm = normalize(clause)
        found = sorted(
            (pos, keys[token])
            for token in keys
            if (pos := _mentions(norm, token)) >= 0
        )
        owners = [name for _, name in found]
        target = owners[0] if owners else current
        current = target
        score = _sentiment(clause)
        if score:
            scores[target] = scores.get(target, 0) + score
    return scores


def _strengths_warnings(form: str | None,
                        polarity: dict[str, tuple[int, int]]) -> tuple[list[str], list[str]]:
    """نقاط قوت و هشدارهای یک استاد از فرم استادشناسی + هم‌جهتی نظرات."""
    strengths: list[str] = []
    warnings: list[str] = []
    # موضوع‌هایی که فرم درباره‌شان حرف زده؛ دیگر از شمارش نظرها تکرار نمی‌شوند
    covered: set[str] = set()

    grading = _form_text(form, "نمره‌دهی")
    if grading:
        if any(word in grading for word in ("ارفاق", "دست باز", "خوب")):
            strengths.append(f"نمره‌دهی: {grading}")
            covered.add("نمره‌دهی")
        elif any(word in grading for word in ("سخت", "کم", "بد")):
            warnings.append(f"نمره‌دهی: {grading}")
            covered.add("نمره‌دهی")

    attendance = _form_text(form, "حضور")
    if attendance:
        if any(word in attendance for word in ("نمی", "مهم نیست", "سختگیر نیست", "حساس نیست")):
            strengths.append("روی حضور و غیاب سختگیر نیست")
        else:
            warnings.append("حضور و غیاب برگزار می‌شود و برایش مهم است")
        covered.add("حضور و غیاب")

    resources = _form_text(form, "منابع")
    if resources:
        if resources.startswith("بله"):
            strengths.append("منابع معرفی‌شده برای امتحان کافی است")
        elif resources.startswith("خیر"):
            warnings.append("منابع کلاس برای امتحان کافی نیست")
        elif "تاحدودی" in resources or "تا حدی" in resources:
            warnings.append("کفایت منابع برای امتحان: تا حدی")

    for theme, (pos, neg) in polarity.items():
        if theme in covered:
            continue
        if pos - neg >= 2:
            strengths.append(THEME_POSITIVE[theme])
        elif neg - pos >= 2:
            warnings.append(THEME_NEGATIVE[theme])

    def unique(items: list[str], limit: int = 4) -> list[str]:
        seen: list[str] = []
        for item in items:
            if item not in seen:
                seen.append(item)
        return seen[:limit]

    strengths, warnings = unique(strengths), unique(warnings)
    # یک نکته ممکن است در دو دسته بیاید؛ تکرار حذف می‌شود
    warnings = [item for item in warnings if item not in strengths]
    return strengths, warnings


def _quality_index(scores: dict[str, int], positive: int, negative: int) -> float | None:
    """شاخص ۰ تا ۱۰ برای مقایسه‌ی دو استاد (امتیاز فرم، وگرنه نسبت نظرها)."""
    if scores:
        return sum(scores.values()) / len(scores)
    if positive + negative:
        return 5 + 5 * (positive - negative) / (positive + negative)
    return None


def professor_profile(store, name: str) -> dict | None:
    """همه‌ی چیزهایی که از داده درباره‌ی یک استاد می‌دانیم، در یک ساختار."""
    professor = next(
        (p for p in store.professors if p.norm_name == normalize(name)), None
    )
    if professor is None:
        return None

    comments = professor.comments
    keys = _name_keys(store)
    entries: list[tuple[str, int]] = []
    for comment in comments:
        if _is_question(comment):
            continue
        mixed = _attributed(comment, keys, professor.name)
        entries.append((comment, mixed.get(professor.name, 0)))

    form = _form(comments)
    scores = _scores(form)
    polarity = _theme_polarity(entries)
    opinions = [score for _, score in entries]
    positive = sum(1 for score in opinions if score > 0)
    negative = sum(1 for score in opinions if score < 0)
    evidence = sum(1 for c in comments if _is_opinion(c))
    strengths, warnings = _strengths_warnings(form, polarity)

    return {
        "name": professor.name,
        "comments": len(comments),
        "form": form,
        "scores": scores,
        "polarity": polarity,
        "positive": positive,
        "negative": negative,
        "neutral": len(comments) - positive - negative,
        "evidence": evidence,
        "strengths": strengths,
        "warnings": warnings,
        "verdict": _verdict(scores, positive, negative, evidence),
        "index": _quality_index(scores, positive, negative),
    }


def professor_answer(store, name: str, course: str = "") -> str | None:
    """نتیجه‌گیری ربات درباره‌ی یک استاد (بدون نقل‌قول از پیام‌ها)."""
    profile = professor_profile(store, name)
    if profile is None:
        return None

    lines = [
        f"👤 {profile['name']} · بر پایه‌ی {_fa(profile['comments'])} پیام آرشیو",
        f"🎯 نتیجه: {profile['verdict']}",
    ]

    scores = profile["scores"]
    if scores:
        average = sum(scores.values()) / len(scores)
        lines.append(f"📊 ارزیابی دانشجویان: {_fa(f'{average:.1f}')} از ۱۰")
        lines.append("   " + " · ".join(f"{k} {_fa(v)}" for k, v in scores.items()))
    elif profile["positive"] or profile["negative"]:
        lines.append(f"🗣 نظرها: {_fa(profile['positive'])} مثبت · "
                     f"{_fa(profile['negative'])} منفی")

    notes: list[str] = []
    touched = profile["positive"] + profile["negative"]
    if not profile["strengths"] and not profile["warnings"] and profile["evidence"] and not course:
        if touched < 4:
            notes.append("نظرهای ثبت‌شده برای این استاد کم است؛ ارزیابی قطعی نیست.")
        else:
            notes.append("نظرها پراکنده است و جمع‌بندی روشن نمی‌دهد؛ "
                         "برای تصمیم بهتر نام درس را هم بپرس.")
    if not scores and not profile["evidence"]:
        notes.append("در آرشیو ارزیابی روشنی درباره‌ی این استاد ثبت نشده است.")

    if profile["strengths"]:
        lines.append("")
        lines.append("✅ نقاط قوت")
        lines.extend(f"• {item}" for item in profile["strengths"])
    if profile["warnings"]:
        lines.append("")
        lines.append("⚠️ نکات مهم")
        lines.extend(f"• {item}" for item in profile["warnings"])
    if notes:
        lines.append("")
        lines.extend(f"ℹ️ {item}" for item in notes)

    courses = courses_for_professor(store, profile["name"], course_norm=course)
    if courses:
        lines.append("")
        lines.append(f"📚 ارائه‌های این استاد در «{_cell(course)}»" if course
                     else "📚 ارائه‌ی این ترم")
        lines.extend(courses)

    return "\n".join(lines)


BETTER = r"(?:بهتر|به\s*تر|درست\s*تر|راحت\s*تر|سنگین\s*تر|کم\s*ریسک\s*تر|انتخاب\s*بهتر)"


def _surname(name: str) -> str:
    tokens = normalize(name).split()
    return tokens[-1] if tokens else ""


def _comparative_votes(store, names: list[str], extra_comments: list[str] | None = None
                       ) -> tuple[dict[str, int], int]:
    """رأی‌های مستقیم «کدام بهتر است» از پیام‌هایی که هر دو استاد را نام می‌برند.

    خروجی: (امتیاز هر استاد، تعداد مقایسه‌های صریح). جمله‌های پرسشی («X بهتره یا Y؟»)
    شمرده نمی‌شوند، چون نظری در خود ندارند.
    """
    names = [n for n in names if _surname(n)]
    if len(names) < 2:
        return {n: 0 for n in names}, 0

    pattern = "|".join(re.escape(_surname(n)) for n in names)
    better_then = re.compile(rf"({pattern})\s*(?:هم|خیلی|یکم|کمی|واقعا|که|اصلا)?\s*{BETTER}")
    better_from = re.compile(rf"{BETTER}\s*(?:از|نسبت\s*به)\s*({pattern})")
    worse_from = re.compile(rf"از\s*({pattern})\s*بدتر")
    better_than_named = re.compile(
        rf"(?:در\s*مقابل|نسبت\s*به|از)\s*({pattern})[^.؟?]*?{BETTER}"
    )

    def resolve(token_text: str) -> str | None:
        for name in names:
            if token_text.startswith(_surname(name)):
                return name
        return None

    votes = {name: 0 for name in names}
    comparisons = 0
    comments: list[str] = list(extra_comments or [])
    for name in names:
        professor = next((p for p in store.professors if p.name == name), None)
        if professor:
            comments.extend(professor.comments)

    seen: set[str] = set()
    for comment in comments:
        norm = normalize(comment)
        if norm in seen or _is_question(comment):
            continue
        seen.add(norm)
        mentioned = [n for n in names if _mentions(norm, _surname(n)) >= 0]
        if len(mentioned) < 2:
            continue

        found_here = False
        # «X بهتر است»
        for match in better_then.finditer(norm):
            name = resolve(match.group(1))
            if name:
                votes[name] += 1
                found_here = True
        # «بهتر از X» ⇒ به زیان X
        for match in better_from.finditer(norm):
            name = resolve(match.group(1))
            if name:
                votes[name] -= 1
                found_here = True
        # «از X بدتر» ⇒ به سود X
        for match in worse_from.finditer(norm):
            name = resolve(match.group(1))
            if name:
                votes[name] += 1
                found_here = True
        # «در مقابل X انتخاب بهتری است» ⇒ به سود دیگری، به زیان X
        for match in better_than_named.finditer(norm):
            name = resolve(match.group(1))
            if name:
                votes[name] -= 1
                others = [n for n in mentioned if n != name]
                if len(others) == 1:
                    votes[others[0]] += 1
                found_here = True
        if found_here:
            comparisons += 1
    return votes, comparisons


def compare_answer(store, names: list[str]) -> str | None:
    """مقایسه‌ی دو یا سه استاد و گفتن این‌که کدام برای انتخاب کم‌ریسک‌تر است."""
    profiles = [p for p in (professor_profile(store, n) for n in names) if p]
    if len(profiles) < 2:
        return None

    label = "، ".join(p["name"] for p in profiles)
    votes, comparisons = _comparative_votes(store, [p["name"] for p in profiles])

    lines = [f"⚖️ مقایسه‌ی {label}"]

    # ۱) اگر آرشیو مقایسه‌ی مستقیم دارد، همان تعیین‌کننده است.
    order = sorted(votes.items(), key=lambda item: item[1], reverse=True)
    top_name, top_vote = order[0]
    spread = top_vote - order[-1][1]
    if comparisons and spread >= 1:
        lines.append(f"🎯 نتیجه: نظرهای آرشیو به «{top_name}» متمایل‌تر است؛ "
                     f"{_fa(comparisons)} مقایسه‌ی مستقیم ثبت شده و نتیجه به سود "
                     "اوست.")
    else:
        # ۲) وگرنه شاخص کیفیت (امتیاز فرم یا نسبت نظرها)
        ranked = sorted((p for p in profiles if p["index"] is not None),
                        key=lambda p: p["index"], reverse=True)
        empty = [p["name"] for p in profiles if p["index"] is None]
        if not ranked:
            lines.append("🎯 نتیجه: داده‌ی کافی برای مقایسه‌ی این اساتید در آرشیو نیست.")
        elif len(ranked) == 1:
            only = ranked[0]
            lines.append(f"🎯 نتیجه: در آرشیو فقط برای «{only['name']}» نظر ثبت شده "
                         f"({_fa(only['positive'])} مثبت · {_fa(only['negative'])} منفی) "
                         f"و برای {'، '.join('«' + n + '»' for n in empty)} ارزیابی "
                         "روشنی نیست؛ تصمیم با خودت، اما داده درباره‌ی اولی حرف می‌زند.")
        elif ranked[0]["index"] >= 8 and ranked[1]["index"] >= 8:
            lines.append("🎯 نتیجه: ارزیابی هر دو خوب است؛ تفاوت معناداری بین آن‌ها "
                         "در آرشیو دیده نمی‌شود و انتخاب به ساعت کلاس بستگی دارد.")
        elif ranked[0]["index"] - ranked[1]["index"] >= 0.5:
            best = ranked[0]
            if best["index"] < 4.5:
                lines.append(f"🎯 نتیجه: هیچ‌کدام ارزیابی مثبتی ندارند، ولی "
                             f"«{best['name']}» کم‌ریسک‌تر است.")
            else:
                lines.append(f"🎯 نتیجه: «{best['name']}» انتخاب کم‌ریسک‌تری است.")
        else:
            lines.append("🎯 نتیجه: تفاوت معناداری بین این اساتید در آرشیو دیده "
                         "نمی‌شود؛ بر اساس ساعت کلاس و درس تصمیم بگیر.")

    lines.append("")
    for profile in profiles:
        marks = [f"{_fa(profile['comments'])} پیام",
                 f"{_fa(profile['positive'])} نظر مثبت",
                 f"{_fa(profile['negative'])} نظر منفی"]
        if profile["scores"]:
            average = sum(profile["scores"].values()) / len(profile["scores"])
            marks.insert(0, f"فرم: {_fa(f'{average:.1f}')} از ۱۰")
        lines.append(f"👤 {profile['name']} — " + " · ".join(marks))
        if profile["strengths"]:
            lines.append(f"   ✅ {profile['strengths'][0]}")
        if profile["warnings"]:
            lines.append(f"   ⚠️ {profile['warnings'][0]}")
        if not (profile["strengths"] or profile["warnings"]):
            lines.append(f"   ℹ️ {profile['verdict']}")

    if comparisons:
        parts = []
        for name, score in order:
            if score > 0:
                parts.append(f"{_fa(score)} به نفع {name}")
            elif score < 0:
                parts.append(f"{_fa(-score)} به زیان {name}")
        if parts:
            lines.append("")
            lines.append("🔁 مقایسه‌های مستقیم: " + " · ".join(parts))

    lines.append("")
    lines.append("📚 این ترم")
    listed = False
    for profile in profiles:
        for row in courses_for_professor(store, profile["name"], limit=2):
            lines.append(f"• {profile['name']} — {row.lstrip('• ')}")
            listed = True
    if not listed:
        lines.append("• برای این اساتید در جدول این ترم درسی ثبت نشده است.")

    lines.append("")
    lines.append("ℹ️ این مقایسه از فرم‌ها و نظرهای آرشیو ساخته شده؛ اگر یکی از این‌ها "
                 "را برای درس مشخصی می‌خواهی، نام درس را هم بگو.")
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

    # «فلانی یا فلانی؟» ⇒ مقایسه، نه دو کارت جدا (به همان ترتیبی که پرسیده شده)
    nquery = normalize(query)
    if len(named) >= 2:
        named.sort(key=lambda name: nquery.find(_surname(name)) % max(len(nquery), 1))
        comparison = compare_answer(store, named[:3])
        if comparison:
            return comparison

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


def sanitize_model_text(text: str, allow_verdict: bool = False,
                       limit: int = 900) -> str:
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
    return "\n".join(lines).strip()[:limit]


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
