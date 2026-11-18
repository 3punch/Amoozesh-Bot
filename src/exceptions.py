"""خطاهای سفارشی ربات آموزش با دسته‌بندی مشخص."""

from __future__ import annotations


class AmoozeshBotError(RuntimeError):
    """خطای پایه‌ی تمام خطاهای ربات."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or "AMOOZESH_ERROR"


class ConfigurationError(AmoozeshBotError):
    """تنظیمات نادرست یا متغیر محیطی遗漏 شده."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="CONFIG_ERROR")


class DataValidationError(AmoozeshBotError):
    """دادهٔ ورودی (Excel/TXT/JSON) مطابق scheme نیست."""

    def __init__(self, message: str, source: str | None = None) -> None:
        super().__init__(message, code="DATA_VALIDATION_ERROR")
        self.source = source


class LLMError(AmoozeshBotError):
    """خطا در ارتباط با مدل محلی یا سرویس ابری."""

    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(message, code="LLM_ERROR")
        self.provider = provider


class QuotaExceededError(AmoozeshBotError):
    """سهمیه‌ی روزانه‌ی کاربر تمام شده است."""

    def __init__(self, user_id: int, kind: str, remaining: int) -> None:
        super().__init__(
            f"سهمیه‌ی {kind} برای کاربر {user_id} تمام شده است",
            code="QUOTA_EXCEEDED",
        )
        self.user_id = user_id
        self.kind = kind
        self.remaining = remaining


class RetrievalError(AmoozeshBotError):
    """خطا در بازیابی یا نرمال‌سازی داده."""

    def __init__(self, message: str, query: str | None = None) -> None:
        super().__init__(message, code="RETRIEVAL_ERROR")
        self.query = query


class VerificationError(AmoozeshBotError):
    """خروجی مدل اعتبارسنجی نشد (عدد/ساعت ساختگی)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason, code="VERIFICATION_ERROR")
        self.reason = reason


class TelegramHandlerError(AmoozeshBotError):
    """خطا در هندلر تلگرام (ارسال پیام، دکمه و غیره)."""

    def __init__(self, message: str, update_id: int | None = None) -> None:
        super().__init__(message, code="TELEGRAM_HANDLER_ERROR")
        self.update_id = update_id