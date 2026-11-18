"""اسکریپت kiểm tra تمام ایمپورت‌های ماژول‌های amoozesh_bot."""

from __future__ import annotations

import sys

MODULES = [
    "amoozesh_bot",
    "amoozesh_bot.exceptions",
    "amoozesh_bot.config",
    "amoozesh_bot.logging_config",
    "amoozesh_bot.models",
    "amoozesh_bot.data_validator",
    "amoozesh_bot.retrieval",
    "amoozesh_bot.bot",
]

failed = []
for mod in MODULES:
    try:
        __import__(mod)
        print(f"✅ {mod}")
    except Exception as exc:
        print(f"❌ {mod}: {exc}")
        failed.append(mod)

if failed:
    print(f"\n{len(failed)} ماژول بارگذاری نشد: {failed}")
    sys.exit(1)
print("\nهمه ماژول‌ها با موفقیت بارگذاری شدند.")
