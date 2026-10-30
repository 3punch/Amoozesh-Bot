"""
ربات دستیار انتخاب واحد — نسخه‌ی مدل محلی.

به‌جای فراخوانی API ابری (OpenRouter) از مدل Gemma که با Ollama روی همان
ماشین اجرا می‌شود استفاده می‌کند؛ بنابراین هیچ API key ای لازم نیست.

اجرا:
    ollama serve            # یا سرویس systemd
    ollama pull gemma3:4b
    TELEGRAM_BOT_TOKEN=... python EntekhabVahedBot.py
"""

import asyncio
import io
import logging
import os
import sys

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

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


async def send_long(message, text: str) -> None:
    """ارسال پاسخ، با شکستن به تکه‌های ۴۰۹۶ کاراکتری."""
    for i, chunk in enumerate(split_message(text)):
        if i == 0:
            await message.reply_text(chunk)
        else:
            await message.reply_text(chunk)


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

    answer = ""
    model_failed = False
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
    if not answer:
        # مدل نبود/خطا داد/خالی جواب داد ⇒ پاسخ قطعی از خود دیتا (بدون تولید آزاد)
        offline = fallback.answer(STORE, user_text)
        if offline:
            log.info("پاسخ قطعی (بدون مدل) ارسال شد.")
            answer = offline + fallback.OFFLINE_NOTE
        else:
            log.error("مدل پاسخ نداد و پاسخی از دیتا هم ساخته نشد.")
            answer = FALLBACK_MESSAGE
    try:
        await placeholder.delete()
    except TelegramError:
        pass

    try:
        await send_long(update.message, answer)
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
    if not llm.wait_for_server(timeout=120):
        log.error("سرویس Ollama در %s بالا نیامد.", llm.OLLAMA_HOST)
        return
    log.info("سرویس Ollama در دسترس است (%s).", llm.OLLAMA_HOST)
    if not llm.model_is_available():
        log.error(
            "مدل «%s» نصب نیست. اجرا کنید: ollama pull %s", llm.MODEL_NAME, llm.MODEL_NAME
        )
        return
    log.info("مدل «%s» آماده است؛ در حال بارگذاری در حافظه…", llm.MODEL_NAME)
    await asyncio.to_thread(llm.preload)


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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("🚀 ربات با مدل محلی «%s» فعال شد!", llm.MODEL_NAME)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
