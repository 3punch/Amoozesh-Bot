# 🎓 Amoozesh-Bot — دقت بالا و حرفه‌ای

ربات تلگرامی فارسی برای انتخاب واحد و بررسی نظرات استادان دانشگاه.

[![CI](https://github.com/3punch/Amoozesh-Bot/actions/workflows/ci.yml/badge.svg)](https://github.com/3punch/Amoozesh-Bot/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-2ea44f.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## ❯ ویژگی‌های کلیدی

| بخش | توضیح |
|------|-------|
| **پاسخ سریع** (Fast Path) | پاسخ از داده‌های ساختاریافته (Excel/TXT) زیر یک ثانیه، بدون صدا زدن مدل |
| **تحلیل مدل** (Deep Mode) | تحلیل با Ollama (محلی) یا API ابری (انتخابی) با اعتبارسنجی خروجی |
| **سهمیه‌ی روزانه** (Quota) | ۳ تحلیل مدل محلی و ۱ تحلیل API برای هر کاربر (بر اساس زمان تهران) |
| **اعتبارسنجی داده** | Pydantic مدل‌ها + اعتبارسنجی فایل‌های ورودی قبل از بارگذاری |
| **لاگ ساختاریافته** | خروجی JSON یا متن، مناسب GitHub Actions و Production |
| **دockerize** | Dockerfile + docker-compose برای اجرا یک‌کلک |

---

## ❯ شروع سریع

### ۱) کلون و راه‌اندازی

`ash
git clone https://github.com/3punch/Amoozesh-Bot.git
cd Amoozesh-Bot
`

### ۲) متغیرهای محیطی

`ash
cp .env.example .env
# .env را باز کنید و TELEGRAM_BOT_TOKEN را تنظیم کنید
`

### ۳) نصب وابستگی‌ها

`ash
# با Makefile
make install

# یا دستی
pip install -r requirements.txt
pip install -e ".[dev]"
`

### ۴) اجرا

`ash
# ربات
make run

# یا با Docker
docker-compose up -d
`

---

## ❯ ساختار پروژه (حرفه‌ای)

`
Amoozesh-Bot/
├── .github/workflows/      # CI/CD (mypy, pytest, bandit)
├── .env.example            # template متغیرهای محیطی
├── .gitignore              # نادیده‌گیری فایل‌های موقت
├── Dockerfile              # ساخت ایمیج ربات
├── docker-compose.yml      # اجرا با Ollama
├── Makefile                # دستورات توسعه (install, test, lint, ...)
├── pyproject.toml          # تنظیمات پروژه و وابستگی‌ها
├── requirements.txt        # وابستگی‌های قفل شده (pinned)
├── README.md               # این فایل
├── EntekhabVahedBot.py     # نقطه‌ی ورود اصلی ربات تلگرام
├── src/                    # لایه حرفه‌ای (نوع-βایمن)
│   ├── __init__.py
│   ├── bot.py              # کلاس AmoozeshBot
│   ├── config.py           # تنظیمات Pydantic
│   ├── exceptions.py       # خطاهای سفارشی
│   ├── logging_config.py   # لاگ ساختاریافته
│   ├── models.py           # مدل‌های داده Pydantic
│   ├── data_validator.py   # اعتبارسنجی داده‌های ورودی
│   └── retrieval.py        # بازیابی داده‌ها و ساخت زمینه
├── tests/                  # تست‌های یکتای و یکپارچه
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   └── test_exceptions.py
├── scripts/                # اسکریپت‌های کمکی
│   └── verify_imports.py   # بررسی بارگذاری ماژول‌ها
└── data/                   # داده‌های runtime (حجم دارد)
`

---

## ❯ تست و کنترل کیفیت

`ash
# همه تست‌ها
make test

# بررسی کد (lint)
make lint

# بررسی نوع (type-check)
make type-check

# بررسی امنیت (security)
make sec

# فرمت‌سازی خودکار
make format

# بررسی ایمپورت‌ها
make verify
`

CI در GitHub Actions در هر push و pull_request روی Python 3.10، 3.11 و 3.12 اجرا می‌شود.

---

## ❯docker-compose

`ash
docker-compose up -d
`

کंटینرهای ollama/ollama برای مدل محلی و ot برای ربات تلگرام اجرا می‌شوند. فایل .env باید در ریشه پروژه وجود داشته باشد.

---

## ❯ مشارکت

1. Fork کنید
2. یک شاخه جدید بسازید: git checkout -b feature/your-feature
3. تغییرات را commit کنید: git commit -m "feat: explain"
4. Push کنید: git push origin feature/your-feature
5. یک Pull Request باز کنید

---

## ❯ مجوز

این پروژه تحت [MIT License](LICENSE) منتشر شده است.

---

> **نکته:** ربات فقط از داده‌های موجود در مخزن پاسخ می‌دهد. برای دقت پایین‌ترین خطا، فایل‌های courses.xlsx، professors.txt و knowledge_base.txt را به‌روز نگه دارید.