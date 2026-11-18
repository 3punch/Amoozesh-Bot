from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from amoozesh_bot.bot import AmoozeshBot


class FakeApplication:
    def __init__(self) -> None:
        self.poll_calls: list[dict[str, Any]] = []

    def run_polling(self, **kwargs: Any) -> None:
        self.poll_calls.append(kwargs)


class FakeBuilder:
    def __init__(self, application: FakeApplication) -> None:
        self.application = application
        self.token_value: str | None = None

    def token(self, value: str) -> FakeBuilder:
        self.token_value = value
        return self

    def build(self) -> FakeApplication:
        return self.application


def test_bot_uses_ptb_owned_polling_lifecycle(monkeypatch, settings) -> None:
    application = FakeApplication()
    builder = FakeBuilder(application)
    datastore_calls: list[Any] = []
    store = SimpleNamespace(professors=[], courses=None, log=[])

    monkeypatch.setattr("amoozesh_bot.bot.setup_logging", lambda **kwargs: None)
    monkeypatch.setattr("amoozesh_bot.bot.ApplicationBuilder", lambda: builder)
    monkeypatch.setattr(
        "amoozesh_bot.bot.DataStore",
        lambda path: datastore_calls.append(path) or store,
    )

    bot = AmoozeshBot(settings)
    bot.run()
    bot.run()

    assert builder.token_value == settings.telegram.token
    assert len(datastore_calls) == 1
    assert application.poll_calls == [
        {"drop_pending_updates": True},
        {"drop_pending_updates": True},
    ]
