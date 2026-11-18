"""تست‌های واحد ماژول تنظیمات (config)."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from src.config import BotSettings, load_settings


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