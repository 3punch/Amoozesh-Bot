"""
ربات دستیار انتخاب واحد — دو حالت پاسخ.

۱) حالت سریع (پیش‌فرض): پاسخ از داده ساخته می‌شود، زیر یک ثانیه. مدل صدا زده نمی‌شود.
۲) حالت مدل: کاربر با دکمه‌ی «🧠 تحلیل با مدل» زیر پاسخ سریع (یا با /deep) از مدل
   می‌خواهد متن کامل نظرها را بخواند و خودش تحلیل کند. روی CPU چند دقیقه طول می‌کشد.

هیچ API key ای لازم نیست؛ مدل با Ollama روی همان ماشین اجرا می‌شود.

اجرا:
    ollama serve                     # فقط برای حالت مدل
    ollama pull qwen2.5:7b
    TELEGRAM_BOT_TOKEN=... python EntekhabVahedBot.py
"""

import asyncio
import io
import logging
import os
import secrets
import sys
import threading
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import deep
import fallback
import llm
from prompts import FALLBACK_MESSAGE, GREETING, build_messages
from retrieval import DataStore

# خروجی UTF-8 بدون از دست رفتن بافر (مهم در ویندوز و لاگ‌های Actions)
try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except (AttributeError, ValueError):  # pragma: no cover
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAX_MESSAGE_LEN = 4000
# چند دقیقه ربات بماند؛ صفر = اجرا تا وقتی متوقف شود (مفید برای اجرای دستی/محلی)
RUN_DURATION_MINUTES = float(os.getenv("RUN_DURATION_MINUTES", "0") or 0)
# آیا جمع‌بندی زبانی مدل خودکار به همه‌ی پاسخ‌ها ضمیمه شود؟
# "0" (پیش‌فرض) = پاسخ فوری از داده‌های قطعی، بدون صدا زدن مدل و بدون Ollama.
# "1" = یک جمع‌بندی کوتاه مدل هم اضافه می‌شود (روی CPU کند است).
MODEL_SUMMARY = os.getenv("MODEL_SUMMARY", "0") == "1"
# حالت «تحلیل با مدل» به‌صورت انتخابی: دکمه‌ی زیر پاسخ یا دستور /deep
DEEP_ENABLED = os.getenv("DEEP_MODE", "1") == "1"
# آیا مدل واقعاً در دسترس است؟ (در on_startup بررسی می‌شود)
MODEL_READY = False

DEEP_BUTTON = "🧠 تحلیل با مدل (۳ تا ۶ دقیقه)"
PENDING_TTL = 30 * 60          # دکمه‌ی هر پاسخ نیم ساعت معتبر است
PENDING_MAX = 400              # سقف دکمه‌های فعال (جلوگیری از رشد حافظه)
PENDING: dict[str, dict] = {}  # توکن کوتاه ⇒ {query, user, ts}


def remember_query(query: str, user_id: int | None = None) -> str:
    """پرسش را برای دکمه‌ی تحلیل مدل نگه می‌دارد و یک توکن کوتاه برمی‌گرداند."""
    now = time.time()
    for token, entry in list(PENDING.items()):
        if now - entry["ts"] > PENDING_TTL:
            PENDING.pop(token, None)
    while len(PENDING) >= PENDING_MAX:
        PENDING.pop(next(iter(PENDING)))
    token = secrets.token_hex(4)
    PENDING[token] = {"query": query, "user": user_id, "ts": now}
    return token


def recall_query(token: str) -> dict | None:
    """توکن دکمه را یک‌بار مصرف می‌کند (ضربه‌ی دوم «منقضی» می‌گیرد)."""
    entry = PENDING.pop(token, None)
    if entry is None:
        return None
    if time.time() - entry["ts"] > PENDING_TTL:
        return None
    return entry


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("amoozeshbot")

STORE = DataStore(".")
for _line in STORE.log:
    log.info(_line)


def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """متن بلند را به تکه‌های مجاز تلگرام می‌شکند (اول روی خط، بعد روی کاراکتر)."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = line
        else:
            current += line
    if current.strip():
        chunks.append(current)
    return [c.strip() for c in chunks if c.strip()]


async def send_long(message, text: str, reply_markup=None) -> None:
    """ارسال پاسخ، با شکستن به تکه‌های ۴۰۹۶ کاراکتری (دکمه روی تکه‌ی آخر)."""
    chunks = split_message(text)
    for i, chunk in enumerate(chunks):
        last = i == len(chunks) - 1
        await message.reply_text(chunk, reply_markup=reply_markup if last else None)


def _looks_useful(text: str) -> bool:
    """جمع‌بندی مدل ارزش نمایش دارد؟ (خالی، خیلی کوتاه یا فقط تکرار سوال نه)"""
    clean = text.strip()
    if len(clean) < 25:
        return False
    if "در اطلاعات موجود نیست" in clean and len(clean) < 70:
        return False
    return True


def is_addressed_to_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """در گروه فقط وقتی جواب می‌دهیم که ریپلای به ربات یا منشن باشد."""
    msg = update.message
    if msg.chat.type not in ("group", "supergroup"):
        return True
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.id == context.bot.id:
            return True
    username = context.bot.username
    return bool(username and f"@{username}" in (msg.text or ""))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(GREETING)


def can_offer_deep() -> bool:
    """دکمه‌ی تحلیل مدل فقط وقتی معنا دارد که مدل واقعاً در دسترس باشد."""
    return DEEP_ENABLED and MODEL_READY and not MODEL_SUMMARY


def deep_keyboard(query: str, user_id: int | None = None) -> InlineKeyboardMarkup | None:
    if not can_offer_deep() or not query.strip():
        return None
    token = remember_query(query, user_id)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(DEEP_BUTTON, callback_data=f"deep:{token}")
    ]])


def base_summary(store, query: str) -> str:
    """یک خط داده‌ی پایه که تحلیل مدل روی آن سوار است (برای شفافیت)."""
    parts: list[str] = []
    for name in deep._names_in_query(store, query):
        profile = fallback.professor_profile(store, name) or {}
        parts.append(
            f"{name}: {fallback._fa(profile.get('positive', 0))} مثبت / "
            f"{fallback._fa(profile.get('negative', 0))} منفی از "
            f"{fallback._fa(profile.get('comments', 0))} پیام"
        )
    if not parts:
        facts = fallback.answer(store, query)
        if facts:
            first = facts.strip().splitlines()[0]
            parts.append(first.lstrip("🎯 ").strip())
    return " · ".join(parts)


def data_verdict(facts: str) -> str:
    """خط «🎯 نتیجه/حکم» پاسخ قطعی، برای نمایش کنار تحلیل مدل."""
    for line in (facts or "").splitlines():
        if line.startswith("🎯"):
            return line.strip().lstrip("🎯").strip()
    return ""


def compose_deep_text(store, query: str, result: dict) -> str:
    """متن نهایی پیام حالت مدل: تحلیل مدل یا شفاف‌سازی شکست + پاسخ قطعی."""
    facts = fallback.answer(store, query) or ""
    summary = base_summary(store, query)

    if result.get("ok"):
        lines = [f"🧠 تحلیل مدل ({result.get('model', llm.MODEL_NAME)})", ""]
        lines.append(result["text"].strip())
        if summary:
            lines.append("")
            lines.append(f"📊 داده‌ی پایه: {summary}")
        verdict = data_verdict(facts)
        if verdict:
            # مدل ممکن است اشتباه قضاوت کند؛ حکم محاسبه‌شده از داده همیشه دیده شود
            lines.append(f"🎯 حکم داده (بدون مدل): {verdict}")
        return "\n".join(lines)

    # شکست: صادقانه بگو چرا، و همان پاسخ معتبر داده را نگه دار
    reason = result.get("reason") or "دلیل نامشخص"
    if result.get("model_failed"):
        head = f"⚠️ مدل در دسترس نبود ({reason})."
    elif result.get("text"):
        head = f"⚠️ تحلیل مدل با داده هم‌خوان نبود و نمایش داده نشد ({reason})."
    else:
        head = f"⚠️ مدل تحلیل قابل استنادی نداد ({reason})."
    if facts:
        return f"{head}\nهمان پاسخ داده معتبر است:\n\n{facts}"
    return head


# Ollama روی رانر فقط یک درخواست را هم‌زمان پردازش می‌کند؛ اگر دو نفر دکمه را
# بزنند، درخواست دوم صف می‌شود نه اینکه هر دو کشته شوند یا همدیگر را کند کنند.
DEEP_RUN_LOCK = threading.Lock()


def _analyze_serialized(store, query: str) -> dict:
    with DEEP_RUN_LOCK:
        return deep.analyze(store, query)


async def run_deep(store, query: str) -> str:
    """اجرای تحلیل مدل (در thread جدا و یکی‌یکی، چون چند دقیقه طول می‌کشد)."""
    result = await asyncio.to_thread(_analyze_serialized, store, query)
    log.info(
        "حالت مدل: %s | ok=%s | دلیل=%s | %.1f ثانیه | زمینه %s کاراکتر",
        query[:50], result.get("ok"), result.get("reason"),
        result.get("elapsed", 0), result.get("meta", {}).get("chars"),
    )
    return compose_deep_text(store, query, result)


async def _edit_or_split(query, text: str) -> None:
    """ویرایش پیام؛ اگر بلندتر از سقف تلگرام بود، ادامه را جدا می‌فرستد."""
    chunks = split_message(text) or ["متأسفم، پاسخی آماده نشد."]
    try:
        await query.edit_message_text(chunks[0])
    except BadRequest as exc:
        log.warning("ویرایش پیام ناموفق: %s", exc)
        if query.message is not None:
            await query.message.reply_text(chunks[0])
    for chunk in chunks[1:]:
        if query.message is not None:
            await query.message.reply_text(chunk)


async def deep_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه‌ی «تحلیل با مدل» زیر پاسخ سریع."""
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    token = (query.data or "").split(":", 1)[-1]
    entry = recall_query(token)
    if entry is None:
        await _edit_or_split(
            query, "⌛️ این دکمه منقضی شده است؛ لطفاً پرسش را دوباره بفرست."
        )
        return

    await _edit_or_split(
        query,
        f"🧠 در حال تحلیل متن کامل با مدل «{llm.MODEL_NAME}»…\n"
        "این کار روی CPU بین ۳ تا ۶ دقیقه طول می‌کشد. لازم نیست کاری کنی؛ "
        "نتیجه همین‌جا جایگزین می‌شود.",
    )
    text = await run_deep(STORE, entry["query"])
    await _edit_or_split(query, text)


async def deep_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/deep <سوال> — از همان اول مسیر مدل."""
    if not update.message:
        return
    if not is_addressed_to_bot(update, context):
        return
    question = " ".join(context.args or []).strip()
    if not question:
        await update.message.reply_text(
            "متن پرسش را بعد از دستور بنویس؛ مثال:\n/deep غلامیان یا تهرانیان؟"
        )
        return

    if not MODEL_READY:
        facts = fallback.answer(STORE, question) or ""
        note = ("⚠️ حالت مدل روی این اجرا فعال نیست (Ollama/مدل در دسترس نیست)."
                "\nپاسخ فوری از داده:\n\n")
        await send_long(update.message, note + (facts or GREETING))
        return

    placeholder = await update.message.reply_text(
        f"🧠 در حال تحلیل متن کامل با مدل «{llm.MODEL_NAME}»… (۳ تا ۶ دقیقه)"
    )
    text = await run_deep(STORE, question)
    chunks = split_message(text) or [FALLBACK_MESSAGE]
    try:
        await placeholder.edit_text(chunks[0])
    except BadRequest as exc:
        log.warning("ویرایش پیام ناموفق: %s", exc)
        await update.message.reply_text(chunks[0])
    for chunk in chunks[1:]:
        await update.message.reply_text(chunk)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not is_addressed_to_bot(update, context):
        return

    user_text = update.message.text.strip()
    # حذف منشن ربات از متن سوال، تا در جست‌وجوی کلیدواژه‌ای نویز نسازد
    if context.bot.username:
        user_text = user_text.replace(f"@{context.bot.username}", " ").strip()
    if not user_text:
        return

    placeholder = await update.message.reply_text("در حال بررسی…")
    await update.message.chat.send_action(ChatAction.TYPING)

    context_text, stats = STORE.build_context(user_text)
    log.info(
        "سوال: %s | کلیدواژه‌ها: %s | زمینه: %s کاراکتر (~%s توکن) | استادها: %s | درس‌ها: %s",
        user_text[:60], stats["keywords"], stats["chars"], stats["tokens"],
        stats["professors"], stats["courses"],
    )

    facts = fallback.answer(STORE, user_text)

    # در حالت پیش‌فرض (MODEL_SUMMARY=0) مدل هیچ‌وقت صدا زده نمی‌شود: پاسخ فوری و
    # دقیق از داده‌ها می‌آید و سوال بی‌ربط هم بلافاصله راهنما می‌گیرد.
    answer = ""
    model_failed = False
    if MODEL_SUMMARY:
        try:
            answer = await asyncio.to_thread(
                llm.generate, build_messages(user_text, context_text)
            )
        except llm.LLMError as exc:
            log.error("خطای مدل: %s", exc)
            model_failed = True
        except Exception:  # noqa: BLE001
            log.exception("خطای پیش‌بینی‌نشدهٔ مدل")
            model_failed = True

    answer = (answer or "").strip()
    answer = fallback.sanitize_model_text(answer, allow_verdict=bool(stats.get("verdict")))

    useful = MODEL_SUMMARY and bool(answer) and _looks_useful(answer)
    if useful:
        ok, why = fallback.verify_model_text(answer, context_text)
        if not ok:
            log.warning("جمع‌بندی مدل رد شد (%s) — فقط داده‌ی قطعی ارسال می‌شود.", why)
            useful = False

    if facts:
        if useful:
            final = f"{facts}\n\n🤖 جمع‌بندی مدل:\n{answer}"
        else:
            final = facts + (fallback.OFFLINE_NOTE if model_failed else "")
        log.info("پاسخ قطعی ارسال شد (جمع‌بندی مدل: %s | مدل صدا زده شد: %s).",
                 useful, MODEL_SUMMARY)
    elif answer:
        final = answer
    elif not MODEL_SUMMARY:
        log.info("سوال خارج از دیتا و جمع‌بندی مدل خاموش است ⇒ راهنما ارسال شد.")
        final = GREETING
    else:
        log.error("نه مدل پاسخ داد و نه پاسخی از دیتا ساخته شد.")
        final = FALLBACK_MESSAGE
    answer = final
    try:
        await placeholder.delete()
    except TelegramError:
        pass

    # دکمه‌ی «تحلیل با مدل» فقط زیر پاسخ واقعی داده می‌آید (نه پیام راهنما)
    keyboard = None
    if facts:
        user = getattr(update.message, "from_user", None)
        keyboard = deep_keyboard(user_text, getattr(user, "id", None))

    try:
        await send_long(update.message, answer, reply_markup=keyboard)
    except BadRequest as exc:
        log.error("ارسال پاسخ ناموفق: %s", exc)
        await update.message.reply_text(FALLBACK_MESSAGE)


async def auto_stop(app, minutes: float) -> None:
    """بعد از مدت مشخص، polling را تمیز می‌بندد (برای چرخش بین runهای Actions)."""
    await asyncio.sleep(minutes * 60)
    log.info("زمان اجرای برنامه‌ریزی‌شده (%.0f دقیقه) تمام شد؛ خاموشی تمیز.", minutes)
    await app.stop()


async def on_startup(app) -> None:
    if RUN_DURATION_MINUTES > 0:
        app.create_task(auto_stop(app, RUN_DURATION_MINUTES))
        log.info("این نمونه %.0f دقیقه اجرا می‌شود، سپس جایش را به run بعدی می‌دهد.",
                 RUN_DURATION_MINUTES)
    global MODEL_READY
    if not (MODEL_SUMMARY or DEEP_ENABLED):
        log.info("هم MODEL_SUMMARY و هم DEEP_MODE خاموش‌اند ⇒ پاسخ‌ها فقط از داده "
                 "ساخته می‌شوند؛ نیازی به Ollama نیست.")
        return
    if not llm.wait_for_server(timeout=120):
        log.error("سرویس Ollama در %s بالا نیامد؛ حالت مدل غیرفعال می‌ماند.",
                  llm.OLLAMA_HOST)
        return
    log.info("سرویس Ollama در دسترس است (%s).", llm.OLLAMA_HOST)
    if not llm.model_is_available():
        log.error(
            "مدل «%s» نصب نیست (ollama pull %s)؛ حالت مدل غیرفعال می‌ماند.",
            llm.MODEL_NAME, llm.MODEL_NAME,
        )
        return
    log.info("مدل «%s» آماده است؛ در حال بارگذاری در حافظه…", llm.MODEL_NAME)
    await asyncio.to_thread(llm.preload)
    MODEL_READY = True
    log.info("حالت «تحلیل با مدل» فعال شد (دکمه‌ی زیر پاسخ + /deep).")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        log.error("متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است.")
        raise SystemExit(1)

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(on_startup)
        .build()
    )
    app.add_handler(CommandHandler(["start", "help"], start_command))
    app.add_handler(CommandHandler("deep", deep_command))
    app.add_handler(CallbackQueryHandler(deep_callback, pattern=r"^deep:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info(
        "🚀 ربات فعال شد | پاسخ سریع: همیشه | حالت مدل «%s»: %s",
        llm.MODEL_NAME, "فعال" if MODEL_READY else "غیرفعال",
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
