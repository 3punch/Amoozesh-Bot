# Amoozesh-Bot

دستیار تلگرامی فارسی برای انتخاب واحد و آشنایی با تجربه‌های ثبت‌شده درباره‌ی استادان. پاسخ سریع از داده‌های پروژه ساخته می‌شود؛ تحلیل اختیاری با Ollama یا API انجام می‌شود.

[![CI](https://github.com/3punch/Amoozesh-Bot/actions/workflows/ci.yml/badge.svg)](https://github.com/3punch/Amoozesh-Bot/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-2ea44f.svg)](LICENSE)

## قابلیت‌ها

- پاسخ سریع و قطعی از فایل‌های دروس، محدودیت‌های ورودی و بازخوردهای استادان؛ بدون نیاز به اجرای مدل.
- تحلیل تکمیلی در صورت درخواست، با Ollama محلی یا API سازگار.
- سهمیه‌ی روزانه برای تحلیل‌های مدل و فایل پایدار وضعیت سهمیه.
- اعتبارسنجی تنظیمات و داده‌ها، و گزارش روشن خطاهای ورودی.
- آزمون‌های آفلاین، مجموعه‌ی ارزیابی طلایی، lint، بررسی نوع، اسکن امنیتی و حداقل پوشش آزمون.

## راه‌اندازی محلی

نیازمندی‌ها: Python 3.10 یا جدیدتر و توکن ربات از BotFather.

```bash
git clone https://github.com/3punch/Amoozesh-Bot.git
cd Amoozesh-Bot
cp .env.example .env
```

مقدار `TELEGRAM_BOT_TOKEN` را در `.env` با توکن واقعی جایگزین کنید. نصب توسعه (شامل وابستگی‌های اجرایی و ابزارهای بررسی کیفیت) و اجرا:

```bash
python -m pip install -e ".[dev]"
python EntekhabVahedBot.py
```

پاسخ سریع بدون Ollama نیز کار می‌کند. برای تحلیل محلی، Ollama را اجرا و مدل تنظیم‌شده در `MODEL_NAME` را دریافت کنید؛ یا برای تحلیل API، کلید را در `API_KEY` قرار دهید.

## اجرا با Docker Compose

فایل `.env` را مطابق بخش قبل بسازید، سپس:

```bash
docker compose up --build -d
```

Compose سرویس Ollama و ربات را اجرا می‌کند. داده‌های فعلی پروژه داخل image ربات قرار دارند و وضعیت سهمیه در volume پایدار `bot_state` ذخیره می‌شود. برای فعال کردن تحلیل محلی، مدل را یک‌بار دریافت کنید:

```bash
docker compose exec ollama ollama pull qwen2.5:7b
```

برای دیدن گزارش‌ها یا توقف سرویس‌ها:

```bash
docker compose logs -f bot
docker compose down
```

توکن واقعی را commit نکنید و `.env` را در اختیار افراد غیرمجاز نگذارید. پورت Ollama در میزبان فقط روی loopback منتشر می‌شود؛ خود ربات از شبکه‌ی داخلی Compose به آن وصل می‌شود.

## داده‌ها

فایل‌های اصلی در ریشه‌ی مخزن قرار دارند: `courses.xlsx`، `professors.txt`، `knowledge_base.txt` و `curriculum.pdf`. هنگام به‌روزرسانی داده‌ها برای اجرای Docker، image را دوباره بسازید (`docker compose up --build -d`). پاسخ‌ها بر پایه‌ی محتوای این فایل‌ها هستند؛ کیفیت و تازگی آن‌ها مستقیماً بر پاسخ اثر می‌گذارد.

## توسعه و کنترل کیفیت

```bash
make install
make test        # اجرای آزمون‌ها و اعمال حداقل پوشش ۷۰٪
make lint        # Ruff و بررسی قالب
make type-check  # MyPy
make sec         # Bandit
make verify      # بررسی importهای بسته
```

یا همه‌ی آزمون‌ها را با جزئیات اجرا کنید:

```bash
pytest tests -v --cov-fail-under=70
```

GitHub Actions همین کنترل‌ها را روی Python 3.10، 3.11 و 3.12 اجرا می‌کند.

## ساختار اصلی

- `EntekhabVahedBot.py`: نقطه‌ی ورود و گردش‌کار تلگرام.
- `retrieval.py`, `fallback.py`, `deep.py`: بازیابی داده و پاسخ سریع/تحلیلی.
- `src/amoozesh_bot/`: بسته‌ی پیکربندی‌شده، مدل‌ها، اعتبارسنجی داده، بازیابی و چرخه‌ی عمر ربات.
- `tests/`: آزمون‌های واحد، یکپارچه و آفلاین.
- `.github/workflows/ci.yml`: کنترل‌های کیفیت خودکار.

## مشارکت و مجوز

تغییرات و گزارش‌های باگ از طریق GitHub Issues و Pull Requests پذیرفته می‌شوند. پروژه تحت [MIT License](LICENSE) منتشر شده است.
