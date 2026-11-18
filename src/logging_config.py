"""لاگ‌ساز ساختاریافته (JSON) برای ربات آموزش."""

from __future__ import annotations

import logging
import logging.config
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    """فارماتر JSON برای لاگ‌های ماشین‌خوانی (مناسب GitHub Actions و Production)."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_obj: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, ensure_ascii=False)


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """راه‌اندازی لاگ‌ساز ربات.

    Args:
        level: سطح لاگ (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_logs: اگر True باشد، خروجی در قالب JSON است.
    """
    formatter: logging.Formatter
    if json_logs:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # حذف handlerهای قبلی (تراکنده‌ای در ریلودها)
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # لاگ‌های کتابخانه‌های شخص ثالث را کمی خاموش کنیم
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)