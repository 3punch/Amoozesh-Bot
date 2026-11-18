"""تست‌های واحد ماژول خطاها (exceptions)."""

from __future__ import annotations

from src.exceptions import (
    AmoozeshBotError,
    ConfigurationError,
    DataValidationError,
    LLMError,
    QuotaExceededError,
    RetrievalError,
    VerificationError,
)


def test_base_error_code():
    err = AmoozeshBotError("something", code="TEST")
    assert err.message == "something"
    assert err.code == "TEST"


def test_quota_exceeded_fields():
    err = QuotaExceededError(user_id=7, kind="deep", remaining=0)
    assert err.user_id == 7
    assert err.kind == "deep"
    assert err.remaining == 0
    assert "deep" in str(err)


def test_verification_error_reason():
    err = VerificationError("عدد ساختگی")
    assert err.reason == "عدد ساختگی"
    assert err.code == "VERIFICATION_ERROR"