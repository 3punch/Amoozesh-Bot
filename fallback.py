"""
پاسخ‌دهی قطعی (بدون مدل).

اگر مدل محلی بالا نیامد، پاسخ نداد یا خروجی خالی داد، ربات با همین ماژول از
دیتای خود پروژه جواب می‌سازد تا کاربر هرگز بی‌جواب نماند و اطلاعات ساختگی نگیرد.

همه‌ی اعداد و جمله‌ها مستقیماً از courses.xlsx / professors.txt / knowledge_base.txt
خوانده می‌شوند؛ هیچ تولید متنی آزادی در کار نیست.
"""

from __future__ import annotations

import re

from retrieval import OPINION_MARKERS, QUESTION_MARKERS, prioritize_comments

FORM_ITEM = {
    "پیوستگی تدریس": r"پیوستگی و یکپارچگی تدریس:\s*(\d+)",
    "تسلط": r"دانش عمومی و تسلط:\s*(\d+)",
    "پاسخ‌گویی": r"پاسخگویی[^:]*:\s*(\d+)",
    "انتقال مطالب": r"توانایی انتقال مطالب:\s*(\d+)",
    "مدیریت کلاس": r"مدیریت کلاس[^:]*:\s*(\d+)",
}
FORM_TEXT = {
    "نمره‌دهی": r"وضعیت نمره دادن:\s*[┘\s]*([^\n📄]+)",
    "حضور و غیاب": r"حضور و غیاب\s*[┘\s]*([^\n📝✅]+)",
    "کفایت منابع": r"منابع معرفی شده برای امتحان کافی است؟\s*[┘\s]*([^\n⭐]+)",
    "توضیح دانشجو": r"توضیحات اضافه:\s*[┘\s]*([^\n➕]+)",
}


FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .،:؛-").translate(FA)


def _is_question(text: str) -> bool:
    return any(m in text for m in QUESTION_MARKERS)


def _best_comments(comments: list[str], limit: int = 3) -> list[str]:
    """نظرهای دارای ارزیابی را جدا می‌کند؛ سوال‌های خالی را دور می‌ریزد."""
    ranked = prioritize_comments(comments)
    solid = [c for c in ranked if not _is_question(c) and any(m in c for m in OPINION_MARKERS)]
    return (solid or [c for c in ranked if not _is_question(c)] or ranked)[:limit]


def _find_form(comments: list[str]) -> str | None:
    """نظر فرم‌مانند (استادشناسی) را برمی‌گرداند؛ کامل‌ترین مورد اولویت دارد."""
    forms = [c for c in comments if "پیوستگی و یکپارچگی تدریس" in c]
    return max(forms, key=len) if forms else None


def professor_card(store, name: str) -> str | None:
    """خلاصه‌ی ساختاریافته‌ی یک استاد از داده‌های آرشیو."""
    prof = next(
        (p for p in store.professors if p.norm_name == store.normalize(name)), None
    )
    if prof is None:
        return None

    lines = [f"«{prof.name}» — بر اساس {len(prof.comments)} پیام موجود در آرشیو:"]

    form = _find_form(prof.comments)
    scores: list[str] = []
    if form:
        for label, pattern in FORM_ITEM.items():
            m = re.search(pattern, form)
            if m:
                scores.append(f"{label} {m.group(1).translate(FA)}/۱۰")
        for label, pattern in FORM_TEXT.items():
            m = re.search(pattern, form)
            if m:
                value = _clean(m.group(1))
                if value and len(value) < 120:
                    lines.append(f"• {label}: {value}")
    if scores:
        lines.append("• امتیازهای فرم استادشناسی: " + "، ".join(scores))

    if len(lines) == 1:
        picks = _best_comments(prof.comments, 3)
        for c in picks:
            short = c if len(c) <= 200 else c[:200] + "…"
            lines.append(f"• {_clean(short)}")
        has_opinion = any(
            not _is_question(c) and any(m in c for m in OPINION_MARKERS)
            for c in prof.comments
        )
        if picks and not has_opinion:
            lines.append("(پیام‌های آرشیو درباره‌ی این استاد بیشتر سوال است؛ ارزیابی ثبت نشده.)")

    courses = store.courses_for_professor(prof.name)
    if courses:
        lines.append("")
        lines.append("📚 ارائه‌ی این ترم:")
        lines.extend(f"• {c}" for c in courses)
    return "\n".join(lines)


def answer(store, query: str, want_model: bool = True) -> str | None:
    """پاسخ قطعی برای سوال، یا None اگر چیزی برای گفتن نبود."""
    verdict = store.check_eligibility(query)
    if verdict:
        text = verdict.split("←", 1)[-1].strip()
        return f"نتیجه: {text}"

    kws = store.keywords(query)
    matches = store.match_professors(kws) if kws else []
    named = [p.name for p, is_named in matches if is_named]
    if named:
        cards = [c for c in (professor_card(store, n) for n in named[:1]) if c]
        if cards:
            return "\n\n".join(cards)

    courses = store.match_courses(kws)
    if courses:
        text = "\n".join(
            f"• {store.format_course_row(r).lstrip('- ')}" for r in courses[:5]
        )
        return "📚 دروس پیدا‌شده در ارائه‌ی این ترم:\n" + text

    return None


def sanitize_model_text(text: str, allow_verdict: bool = False) -> str:
    """خطوط پرخطر مدل را حذف می‌کند (حکمِ بی‌ربط، تکرار سوال، پرحرفی)."""
    if not text:
        return ""
    drop_markers = () if allow_verdict else ("نتیجه: مجاز است", "نتیجه: مجاز نیست")
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # مدل روی سوال‌های غیرِ مجاز بودن هم «نتیجه» می‌سازد؛ این‌ها را نگه نمی‌داریم
        if any(m in stripped for m in drop_markers):
            continue
        lines.append(stripped)
    out = "\n".join(lines).strip()
    return out[:900]


TIME_RE = re.compile(r"\d{1,2}:\d{2}")
NUM_RE = re.compile(r"\d+")
TO_ASCII = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def verify_model_text(text: str, context: str) -> tuple[bool, str]:
    """
    آیا جمع‌بندی مدل با «اطلاعات» سازگار است؟

    همه‌ی ساعت‌ها و اعدادی که مدل می‌نویسد باید عیناً در زمینه باشند؛
    در غیر این صورت متن دور ریخته می‌شود (مدل ۴B ساعت و ظرفیت از خودش می‌سازد).
    """
    if not text.strip():
        return False, "خالی"
    if "اطلاعات موجود نیست" in text:
        return False, "مدل گفت اطلاعاتی نیست (متناقض با داده)"

    def norm(value: str) -> str:
        # ارقام فارسی/عربی → ASCII تا مقایسه‌ی عددی ممکن باشد
        # (خطوط جدید حفظ می‌شوند تا بررسی «ساعت‌های یک خط» معنا داشته باشد)
        value = re.sub(r"[ \t\u200c]+", " ", value.translate(TO_ASCII))
        return value

    ctx = norm(context)
    ctx_times = set(TIME_RE.findall(ctx))
    ctx_nums = set(NUM_RE.findall(ctx))
    ctx_lines = [l for l in ctx.splitlines() if l.strip()]

    out = norm(text)

    # ۱) ساعتی که اصلاً در زمینه نیست
    made_up = [t for t in TIME_RE.findall(out) if t not in ctx_times]
    if made_up:
        return False, f"ساعت ساختگی: {', '.join(made_up[:3])}"

    # ۲) ترکیب اشتباه ساعت‌ها: همه‌ی ساعت‌های یک خط مدل باید در یک خط زمینه باشند
    for line in out.splitlines():
        times = TIME_RE.findall(line)
        if len(times) >= 2 and not any(all(t in l for t in times) for l in ctx_lines):
            return False, f"ترکیب ساعت اشتباه: {' و '.join(times[:3])}"

    # ۳) عددی که در زمینه نیست (ظرفیت، کد درس، امتیاز و…)
    novel = sorted({n for n in NUM_RE.findall(out) if n not in ctx_nums}, key=len, reverse=True)
    if novel:
        return False, f"عدد ساختگی: {', '.join(novel[:3])}"
    return True, "ok"


OFFLINE_NOTE = "\n\n_(مدل محلی در دسترس نبود؛ این پاسخ مستقیم از داده‌های پروژه ساخته شد.)_"
