"""اسکریپت kiểm tra تمام ایمپورت‌های ماژول‌های src."""

from __future__ import annotations

import sys

MODULES = [
    "src",
    "src.exceptions",
    "src.config",
    "src.logging_config",
    "src.models",
    "src.data_validator",
    "src.retrieval",
    "src.bot",
]

failed = []
for mod in MODULES:
    try:
        __import__(mod)
        print(f"✅ {mod}")
    except Exception as exc:  # noqa: BLE001
        print(f"❌ {mod}: {exc}")
        failed.append(mod)

if failed:
    print(f"\n{len(failed)} ماژول بارگذاری نشد: {failed}")
    sys.exit(1)
print("\nهمه ماژول‌ها با موفقیت بارگذاری شدند.")