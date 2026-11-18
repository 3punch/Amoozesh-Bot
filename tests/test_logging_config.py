from __future__ import annotations

import json
import logging
from datetime import datetime

from amoozesh_bot.logging_config import JsonFormatter, setup_logging


def test_json_formatter_emits_machine_readable_unicode() -> None:
    record = logging.LogRecord(
        name="amoozeshbot.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="آزمون موفق بود",
        args=(),
        exc_info=None,
    )
    formatted = json.loads(JsonFormatter().format(record))

    assert formatted["message"] == "آزمون موفق بود"
    assert formatted["level"] == "INFO"
    assert formatted["line"] == 42
    assert datetime.fromisoformat(formatted["ts"]).tzinfo is not None


def test_setup_logging_replaces_existing_handlers() -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    try:
        setup_logging("DEBUG", json_logs=True)
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            handler.close()
        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)
