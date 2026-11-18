"""راه‌اندازی حرفه‌ای ربات آموزش با پیکربندی Pydantic و لاگ ساختاریافته."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from telegram.ext import ApplicationBuilder

from src.config import load_settings
from src.logging_config import setup_logging
from src.retrieval import DataStore

log = logging.getLogger("amoozeshbot")


class AmoozeshBot:
    """گلاف حرفه‌ای برای ربات教學.

    مسئولیت‌ها:
      * بارگذاری پیکربندی و لاگ‌ساز
      * بارگذاری ذخیره‌ی داده‌ها (DataStore)
      * ساخت Application تلگرام
      * اجرایառ cleaning graceful
    """

    def __init__(self, settings=None) -> None:
        self.settings = settings or load_settings()
        setup_logging(level=self.settings.log_level, json_logs=False)
        self.store: DataStore | None = None
        self.app = None

    async def initialize(self) -> None:
        """بارگذاری داده‌ها و آماده‌سازی ربات."""
        log.info("در حال بارگذاری پیکربندی و داده‌ها…")
        self.store = DataStore(str(self.settings.data_dir))
        log.info(
            "داده‌ها بارگذاری شد: %d استاد، %d درس",
            len(self.store.professors) if self.store.professors else 0,
            len(self.store.courses) if self.store.courses is not None else 0,
        )

        self.app = (
            ApplicationBuilder()
            .token(self.settings.telegram.token)
            .build()
        )
        log.info("Application تلگرام ساخته شد.")

    async def run(self) -> None:
        """اجرای ربات تا زمانی که متوقف شود."""
        if self.app is None:
            await self.initialize()

        log.info("ربات در حال اجرا است (polling).")
        await self.app.run_polling(drop_pending_updates=True)

    async def stop(self) -> None:
        """توقف تمیز ربات."""
        if self.app:
            log.info("توقف ربات…")
            await self.app.stop()


def main() -> None:
    """نقطه‌ی ورود canonical."""
    bot = AmoozeshBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        log.info("دستدست توسط کاربر متوقف شد.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        log.exception("خطای commits하지 است: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()