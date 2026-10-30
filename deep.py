"""
حالت «تحلیل مدل» (deep) — وقتی مدل واقعاً متن را می‌خواند و خودش نتیجه می‌گیرد.

حالت پیش‌فرض ربات «سریع» است: پاسخ از داده ساخته می‌شود (fallback.py) و زیر یک
ثانیه برمی‌گردد. این ماژول مسیر دوم را می‌سازد که کاربر با دکمه‌ی «🧠 تحلیل مدل»
یا دستور `/deep` انتخاب می‌کند.

تفاوت اصلی با حالت سریع:
    • به مدل **متن کامل** شناسنامه‌ی استادها داده می‌شود، نه زمینه‌ی ۴۰۰۰ کاراکتری.
    • پرامپت از مدل «فهم» می‌خواهد: کنایه، شوخی، جمله‌ی مشترک دو استاد، لحن کلی.
    • خروجی هنوز اعتبارسنجی می‌شود: ساعت/سال/امتیاز ساختگی رد می‌شود.

علاوه بر متن خام، یک «خلاصه‌ی عددی» هم به مدل می‌دهیم؛ هم به فهمش کمک می‌کند و
هم باعث می‌شود اعدادی که در پاسخ می‌نویسد قابل ردیابی باشند.

متغیرهای محیطی:
    DEEP_CONTEXT_CHARS  سقف متن زمینه‌ی حالت مدل            (پیش‌فرض: 14000)
    DEEP_MAX_TOKENS     حداکثر توکن پاسخ مدل                (پیش‌فرض: 500)
    DEEP_NUM_CTX        اندازه‌ی پنجره‌ی زمینه‌ی حالت مدل    (پیش‌فرض: 8192)
    DEEP_TIMEOUT        مهلت هر درخواست به ثانیه             (پیش‌فرض: 900)
"""

from __future__ import annotations

import os
import re
import time

import fallback
import llm
from prompts import build_analysis_messages
from retrieval import normalize, prioritize_comments

DEEP_CONTEXT_CHARS = int(os.getenv("DEEP_CONTEXT_CHARS", "14000"))
DEEP_MAX_TOKENS = int(os.getenv("DEEP_MAX_TOKENS", "500"))
DEEP_NUM_CTX = int(os.getenv("DEEP_NUM_CTX", "8192"))
DEEP_TIMEOUT = int(os.getenv("DEEP_TIMEOUT", "900"))
MAX_PROFESSORS = 3

# ---------------------------------------------------------------- ساخت زمینه


def _names_in_query(store, query: str) -> list[str]:
    """استادهایی که نامشان در پرسش آمده، به همان ترتیبی که پرسیده شده."""
    nquery = normalize(query)
    found: list[tuple[int, str]] = []
    for professor in store.professors:
        surname = normalize(professor.name).split()[-1]
        position = nquery.find(surname)
        if position >= 0 and len(surname) >= 3:
            found.append((position, professor.name))
    found.sort()
    return [name for _, name in found][:MAX_PROFESSORS]


def _professor_block(store, name: str) -> tuple[str, str]:
    """(خلاصه‌ی عددی، متن کامل نظرات) برای یک استاد."""
    professor = next((p for p in store.professors if p.name == name), None)
    if professor is None:
        return "", ""

    profile = fallback.professor_profile(store, name) or {}
    digest = [
        f"«{professor.name}»",
        f"  پیام‌های آرشیو: {profile.get('comments', 0)}",
        f"  نظر مثبت: {profile.get('positive', 0)} · نظر منفی: {profile.get('negative', 0)}",
    ]
    scores = profile.get("scores") or {}
    if scores:
        average = sum(scores.values()) / len(scores)
        digest.append(f"  میانگین فرم استادشناسی: {average:.1f} از 10")
        digest.append("  امتیازهای فرم: " + " · ".join(f"{k} {v}" for k, v in scores.items()))
    if profile.get("strengths"):
        digest.append("  نکات مثبت استخراج‌شده: " + "؛ ".join(profile["strengths"]))
    if profile.get("warnings"):
        digest.append("  هشدارهای استخراج‌شده: " + "؛ ".join(profile["warnings"]))

    comments = prioritize_comments(professor.comments) or [professor.body]
    body = "\n".join(f"- {c}" for c in comments if c.strip())
    return "\n".join(digest), body


def build_deep_context(store, query: str) -> tuple[str, dict]:
    """زمینه‌ی کامل برای حالت مدل: متن همه‌ی نظرها + خلاصه‌ی عددی + جدول دروس."""
    named = _names_in_query(store, query)
    sections: list[tuple[str, str]] = []
    meta = {"professors": [], "courses": 0, "chars": 0}

    if named:
        digests, bodies = [], []
        for name in named:
            digest, body = _professor_block(store, name)
            if digest:
                digests.append(digest)
            if body:
                bodies.append(f"### {name}\n{body}")
        sections.append(("خلاصه‌ی عددی (این اعداد قابل استناد هستند)", "\n".join(digests)))
        sections.append(("متن کامل نظرات دانشجویان (بدون ویرایش)", "\n\n".join(bodies)))
        meta["professors"] = named

    # جدول دروس همین استادها (یا درس پرسیده‌شده)
    lines: list[str] = []
    for name in named:
        lines.extend(fallback.courses_for_professor(store, name, limit=6))
    if not lines:
        rows = store.match_courses(store.keywords(query))
        lines = [store.format_course_row(row) for row in rows[:8]]
    if lines:
        sections.append(("ارائه‌های این ترم (از جدول رسمی)", "\n".join(lines)))
        meta["courses"] = len(lines)

    info = store.eligibility_info(query)
    if info:
        verdict = "مجاز است" if info["allowed"] else "مجاز نیست"
        sections.append((
            "حکم قطعی مجاز بودن (از knowledge_base؛ این خط درست است)",
            f"«{info['course']}» برای ورودی {info['year']}: {verdict} — {info['reason']}",
        ))

    if not sections:
        # پرسش عمومی: کلیدواژه‌ای نزدیک‌ترین‌ها را می‌آوریم تا مدل دست خالی نماند.
        kws = store.keywords(query)
        for professor, _ in store.match_professors(kws)[:MAX_PROFESSORS]:
            digest, body = _professor_block(store, professor.name)
            if digest:
                sections.append((f"نزدیک‌ترین شناسنامه: {professor.name}",
                                 digest + "\n" + body[:1500]))

    context = "\n\n".join(f"## {title}\n{body}" for title, body in sections)
    if len(context) > DEEP_CONTEXT_CHARS:
        context = context[:DEEP_CONTEXT_CHARS].rstrip() + "\n… (ادامه‌ی متن بریده شد)"
    meta["chars"] = len(context)
    return context, meta


# ---------------------------------------------------------------- اعتبارسنجی

TIME_RE = re.compile(r"\d{1,2}:\d{2}")
YEAR_RE = re.compile(r"\b(1[34]\d{2})\b")
SCORE_RE = re.compile(r"(\d{1,2}(?:\.\d)?)\s*(?:از|/)\s*10\b")
BIG_NUM_RE = re.compile(r"\b\d{3,}\b")
LATIN_RE = re.compile(r"[A-Za-z]{2,}")


def _ascii(text: str) -> str:
    """ارقام فارسی و عربی را به لاتین برمی‌گرداند تا مقایسه‌ی عددی امن باشد."""
    return re.sub(r"[ \t\u200c]+", " ", text.translate(fallback.TO_ASCII))


def verify_analysis_text(text: str, context: str) -> tuple[bool, str]:
    """آیا تحلیل مدل با داده سازگار است؟

    سخت‌گیری روی چیزهایی است که مدل کوچک زیاد می‌سازد و به تصمیم دانشجو آسیب
    می‌زند: ساعت کلاس، سال ورودی، امتیاز. شمارش‌های کوچک (تعداد نظر) آزادند،
    چون خودمان در «خلاصه‌ی عددی» به مدل داده‌ایم.
    """
    if not text.strip():
        return False, "خالی"
    # اگر داده داریم ولی مدل می‌گوید چیزی نیست ⇒ متناقض
    if "اطلاعات موجود نیست" in text and len(context) > 300:
        return False, "مدل گفت اطلاعاتی نیست، در حالی که داده هست"

    ctx = _ascii(context)
    out = _ascii(text)

    ctx_times = set(TIME_RE.findall(ctx))
    made_up_times = [t for t in TIME_RE.findall(out) if t not in ctx_times]
    if made_up_times:
        return False, f"ساعت ساختگی: {', '.join(made_up_times[:3])}"

    ctx_years = set(YEAR_RE.findall(ctx))
    made_up_years = [y for y in YEAR_RE.findall(out) if y not in ctx_years]
    if made_up_years:
        return False, f"سال ساختگی: {', '.join(made_up_years[:3])}"

    # امتیاز باید عیناً در داده باشد؛ «۴ از ۱۰» وقتی داده «۹.۶» دارد ساختگی است.
    for score in SCORE_RE.findall(out):
        variants = {score}
        if "." in score:
            variants.add(score.rstrip("0").rstrip("."))
        if not any(
            re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", ctx) for v in variants
        ):
            return False, f"امتیاز ساختگی: {score}"

    # خروجی مدل باید فارسی باشد؛ حروف لاتین نشانه‌ی متن مخدوش است
    # (در اجرای واقعی «آذرaboالقاسمی» تولید شد).
    latin = LATIN_RE.findall(text)
    if latin:
        return False, f"خروجی غیرفارسی/مخدوش: {', '.join(latin[:3])}"

    fake_big = [n for n in BIG_NUM_RE.findall(out) if n not in ctx]
    if fake_big:
        return False, f"عدد بزرگ ناموجود در داده: {', '.join(fake_big[:3])}"

    if len(text.strip()) < 25:
        return False, "خیلی کوتاه"
    return True, "ok"


# ---------------------------------------------------------------- اجرا


def analyze(store, query: str) -> dict:
    """تحلیل کامل با مدل. خروجی همیشه یک dict است؛ خطا استثنا نمی‌دهد."""
    context, meta = build_deep_context(store, query)
    started = time.time()

    if not context.strip():
        return {"ok": False, "text": "", "reason": "برای این پرسش داده‌ای پیدا نشد",
                "model_failed": False, "elapsed": 0.0, "meta": meta, "raw": ""}

    try:
        raw = llm.generate(
            build_analysis_messages(query, context),
            max_tokens=DEEP_MAX_TOKENS,
            num_ctx=DEEP_NUM_CTX,
            timeout=DEEP_TIMEOUT,
            temperature=0.3,
        )
    except llm.LLMError as exc:
        return {"ok": False, "text": "", "reason": str(exc), "model_failed": True,
                "elapsed": round(time.time() - started, 1), "meta": meta, "raw": ""}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "text": "", "reason": f"خطای پیش‌بینی‌نشده: {exc}",
                "model_failed": True, "elapsed": round(time.time() - started, 1),
                "meta": meta, "raw": ""}

    text = fallback.sanitize_model_text(raw, allow_verdict=True, limit=2500)
    ok, why = verify_analysis_text(text, context)
    result = {
        "ok": ok,
        "text": text if ok else "",
        "reason": why,
        "model_failed": False,
        "elapsed": round(time.time() - started, 1),
        "meta": meta,
        "raw": raw,
        "model": llm.MODEL_NAME,
        "stats": dict(llm.LAST_STATS),
    }
    return result
