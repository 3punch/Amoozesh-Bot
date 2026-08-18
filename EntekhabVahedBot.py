import sys
import io
import requests
import pandas as pd
from pypdf import PdfReader
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

import os  

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')



def load_data():

    try:
        df = pd.read_excel('courses.xlsx')
        courses_str = df.to_string(index=False)
        print("✅ فایل ارائه دروس (courses.xlsx) بارگذاری شد.")
    except Exception as e:
        courses_str = "فایل ارائه دروس یافت نشد."


    professors_list = []
    try:
        with open('professors.txt', 'r', encoding='utf-8') as f:
            content = f.read()
            professors_list = [p.strip() for p in content.split("\n---\n") if p.strip()]
        print(f"✅ تعداد {len(professors_list)} پیام استادشناسی بارگذاری شد.")
    except Exception as e:
        print(f"⚠️ خطا در خواندن professors.txt: {e}")


    curriculum_str = ""
    try:
        reader = PdfReader("curriculum.pdf")
        for page in reader.pages:
            text = page.extract_text()
            if text:
                curriculum_str += text + "\n"
        print("✅ فایل چارت درسی (curriculum.pdf) بارگذاری شد.")
    except Exception:
        curriculum_str = "فایل چارت آموزشی یافت نشد."


    knowledge_base_str = ""
    try:
        with open('knowledge_base.txt', 'r', encoding='utf-8') as f:
            knowledge_base_str = f.read()
        print("✅ فایل قوانین ورودی‌ها (knowledge_base.txt) بارگذاری شد.")
    except Exception as e:
        print(f"⚠️ خطا در خواندن knowledge_base.txt: {e}")
        knowledge_base_str = "اطلاعاتی درباره محدودیت ورودی‌ها یافت نشد."

    return courses_str, professors_list, curriculum_str, knowledge_base_str


COURSES_DATA, PROFESSORS_LIST, CURRICULUM_DATA, KNOWLEDGE_BASE_DATA = load_data()

def get_relevant_comments(user_query, max_items=15):
    """پیدا کردن سریع فقط پیام‌های مرتبط با سوال کاربر"""
    if not PROFESSORS_LIST:
        return "هیچ نظری در فایل یافت نشد."

    query_words = [w.strip() for w in user_query.split() if len(w.strip()) > 1]
    ignore_words = {'استاد', 'دکتر', 'چطوره', 'چطور', 'خوبه', 'درس', 'ترم', 'ارائه', 'نظرت', 'درباره', 'مورد', 'بهم', 'بگو'}
    search_keywords = [w for w in query_words if w not in ignore_words]

    if not search_keywords:
        return "لطفاً نام استاد یا درس مورد نظر را وارد کنید."

    matched = []
    for msg in PROFESSORS_LIST:
        if any(keyword in msg for keyword in search_keywords):
            matched.append(msg)
            if len(matched) >= max_items:
                break

    if matched:
        print(f"⚡ {len(matched)} نظر مرتبط پیدا شد.")
        return "\n\n---\n\n".join(matched)
    else:
        print("⚠️ هیچ نظری با این اسم پیدا نشد.")
        return "هیچ نظر مستقیمی درباره این نام در آرشیو یافت نشد."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    chat_type = update.message.chat.type

    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        is_replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
        is_mentioned = f"@{bot_username}" in user_text if bot_username else False
        if not (is_replied or is_mentioned):
            return

    await update.message.reply_text("Amoozeshbot is Thinking...")

    relevant_comments = get_relevant_comments(user_text)


    system_prompt = f"""
تو یک مشاور دقیق و هوشمند انتخاب واحد هستی.

[قوانین و مجاز بودن دروس برای ورودی‌های مختلف]
{KNOWLEDGE_BASE_DATA}

[ارائه دروس این ترم]
{COURSES_DATA}

[نظرات پیدا شده درباره استاد/درس]
{relevant_comments}

[چارت درسی]
{CURRICULUM_DATA}

دستورالعمل:
۱. اگر کاربر درباره مجاز بودن یک درس برای ورودی خاصی پرسید، حتماً بخش [قوانین و مجاز بودن دروس] را چک کن و با دقت بگو آیا آن ورودی مجاز به اخذ آن درس هست یا خیر.
۲. بر اساس [نظرات پیدا شده]، خلاصه‌ای از اخلاق، تدریس و نمره‌دهی استاد بگو.
۳. اگر درباره استادی نظری یافت نشد، بگو نظري ثبت نشده اما وضعیت ارائه درسش را از جدول ارائه دروس بگو.
۴. پاسخ‌ها کوتاه، مفید و دقیق باشند.
"""

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openrouter/auto", 
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ]
            },
            timeout=60
        )
        
        result = response.json()
        if "choices" in result:
            reply = result["choices"][0]["message"]["content"]
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text("خطا در پاسخ‌دهی سرور.")
            
    except Exception as e:
        await update.message.reply_text("لطفا پرامپت دیگری وارد کنید")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("\n🚀 ربات با قابلیت بررسی ورودی‌ها فعال شد!")
    app.run_polling()