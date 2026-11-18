"""فیکسچرهای مشترک برای تست‌های ربات آموزش."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# ایzolate محیط تست از متغیرهای الحقيقي
os.environ["QUOTA_PERSIST"] = "0"
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token_123:ABC"
os.environ["GITHUB_TOKEN"] = ""
os.environ["GITHUB_REPOSITORY"] = ""
os.environ["API_KEY"] = ""


@pytest.fixture
def tmp_data_dir():
    """دیکتری موقت برای داده‌های تست."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def settings():
    """تنظیمات پیش‌فرض برای تست."""
    from src.config import load_settings
    return load_settings()