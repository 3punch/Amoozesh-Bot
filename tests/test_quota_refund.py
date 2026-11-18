import asyncio
from typing import Any

import EntekhabVahedBot as bot


class FakeQuota:
    def __init__(self) -> None:
        self.refunded: list[tuple[int, str]] = []

    def consume(self, user_id: int, kind: str) -> bool:
        return True

    def refund(self, user_id: int, kind: str) -> None:
        self.refunded.append((user_id, kind))


def test_unexpected_analysis_exception_refunds_quota(monkeypatch: Any) -> None:
    quota = FakeQuota()

    def fail_analysis(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("temporary provider failure")

    monkeypatch.setattr(bot, "QUOTA", quota)
    monkeypatch.setattr(bot.deep, "analyze", fail_analysis)

    response = asyncio.run(bot.run_deep(store=None, query="test", provider="local", user_id=901))

    assert quota.refunded == [(901, "deep")]
    assert "موقتاً در دسترس نیست" in response
    assert "temporary provider failure" not in response
