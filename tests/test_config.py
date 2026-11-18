"""تست‌های واحد ماژول تنظیمات (config)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from amoozesh_bot.config import BotSettings, QuotaSettings, load_settings


def test_default_settings_load(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    settings = load_settings()
    assert isinstance(settings, BotSettings)
    assert settings.telegram.token == "123:abc"
    assert settings.retrieval.max_context_chars == 4000


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ValidationError):
        load_settings()


def test_llm_host_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434/")
    settings = load_settings()
    assert settings.llm.ollama_host == "http://127.0.0.1:11434"


def test_blank_token_is_rejected(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "   ")
    with pytest.raises(ValidationError):
        load_settings()


def test_runtime_tuning_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("MAX_PROF_BLOCK_CHARS", "700")
    monkeypatch.setenv("PENDING_TTL", "120")
    monkeypatch.setenv("PENDING_MAX", "50")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = load_settings()

    assert settings.retrieval.max_prof_block_chars == 700
    assert settings.runtime.pending_ttl == 120
    assert settings.runtime.pending_max == 50
    assert settings.log_level == "DEBUG"


def test_quota_defaults_are_not_shared_between_instances():
    first = QuotaSettings()
    second = QuotaSettings()

    first.limits["deep"] = 0

    assert second.limits["deep"] == 3
