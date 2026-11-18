"""راه‌اندازی لایه‌ی Telegram با lifecycle سازگار با python-telegram-bot."""

from __future__ import annotations

import logging
import sys
from typing import Any

from telegram.ext import Application, ApplicationBuilder

from amoozesh_bot.config import BotSettings, load_settings
from amoozesh_bot.logging_config import setup_logging
from amoozesh_bot.retrieval import DataStore

log = logging.getLogger("amoozeshbot")


class AmoozeshBot:
    """بارگذاری تنظیمات و داده‌ها و اجرای polling مدیریت‌شده‌ی PTB."""

    def __init__(self, settings: BotSettings | None = None) -> None:
        self.settings = settings or load_settings()
        setup_logging(level=self.settings.log_level, json_logs=False)
        self.store: DataStore | None = None
        self.app: Application[Any, Any, Any, Any, Any, Any] | None = None

    def initialize(self) -> None:
        """داده‌ها و برنامه‌ی Telegram را یک‌بار آماده می‌کند."""
        if self.app is not None:
            return

        log.info("در حال بارگذاری پیکربندی و داده‌ها…")
        self.store = DataStore(self.settings.data_dir)
        for message in self.store.log:
            if message.startswith("هشدار:"):
                log.warning("%s", message)
            else:
                log.debug("%s", message)
        log.info(
            "داده‌ها بارگذاری شد: %d استاد، %d درس",
            len(self.store.professors),
            len(self.store.courses) if self.store.courses is not None else 0,
        )
        self.app = ApplicationBuilder().token(self.settings.telegram.token).build()
        log.info("Application تلگرام ساخته شد.")

    def run(self) -> None:
        """اجرای polling؛ run_polling خودش initialize/start/stop را مدیریت می‌کند."""
        self.initialize()
        if self.app is None:  # دفاع در برابر تغییر lifecycle آینده
            raise RuntimeError("Application تلگرام ساخته نشد")
        log.info("ربات در حال اجرا است (polling).")
        self.app.run_polling(drop_pending_updates=True)


def main() -> None:
    """نقطه‌ی ورود؛ PTB باید مالک event loop بماند."""
    bot = AmoozeshBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        log.info("ربات به درخواست کاربر متوقف شد.")
    except Exception:
        log.exception("اجرای ربات با خطا متوقف شد.")
        sys.exit(1)


if __name__ == "__main__":
    main()
