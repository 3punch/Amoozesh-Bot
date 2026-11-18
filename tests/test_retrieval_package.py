from __future__ import annotations

from pathlib import Path

from amoozesh_bot.retrieval import DataStore, estimate_tokens, keywords, normalize

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_normalization_handles_persian_unicode_and_digits() -> None:
    assert normalize("علي كريمي، ورودی ۱۴۰۳") == "علی کریمی ورودی 1403"
    assert "استاد" not in keywords("استاد ایزدیخواه چطوره؟")
    assert estimate_tokens("۱۲۳۴۵۶") == 2


def test_repository_data_is_loaded_and_restrictions_are_deterministic() -> None:
    store = DataStore(REPOSITORY_ROOT)

    assert store.courses is not None and len(store.courses) == 103
    assert len(store.professors) == 35
    assert len(store.entry_rules) == 12
    assert "مجاز نیست" in store.check_eligibility("بهینه سازی خطی برای ورودی ۱۴۰۴ مجازه؟")
    assert "مجاز است" in store.check_eligibility(
        "ساختمان داده و الگوریتم ها برای ورودی ۱۴۰۴ مجازه؟"
    )
    assert store.check_eligibility("استاد ایزدیخواه چطوره؟") == ""


def test_retrieval_targets_named_professors_courses_and_curriculum() -> None:
    store = DataStore(REPOSITORY_ROOT)

    context, stats = store.build_context("استاد ایزدیخواه چطوره؟")
    assert "محمد ایزدیخواه" in context
    assert stats["professors"]
    assert stats["chars"] == len(context)

    offerings = store.match_courses(["همامی"])
    assert offerings
    assert all("همامی" in row["استاد"] for row in offerings)

    curriculum = store._curriculum_snippet(["ریاضی"])
    assert curriculum
    assert len(curriculum) <= 1000


def test_context_keeps_exact_verdict_and_respects_budget(tmp_path: Path) -> None:
    (tmp_path / "knowledge_base.txt").write_text(
        "دروس ویژه دانشجویان ورودی ۱۴۰۳:\nبهینه سازی خطی - استاد نمونه - شنبه 10:00\n",
        encoding="utf-8",
    )
    (tmp_path / "courses.xlsx").write_bytes((REPOSITORY_ROOT / "courses.xlsx").read_bytes())
    (tmp_path / "professors.txt").write_text(
        "=== شناسنامه استاد: استاد نمونه ===\nنظر مفید\n", encoding="utf-8"
    )

    store = DataStore(tmp_path)
    context, stats = store.build_context("بهینه سازی خطی برای ورودی ۱۴۰۴ مجاز است؟")

    assert context.startswith("### پاسخ قطعی")
    assert "مجاز نیست" in stats["verdict"]
    assert stats["chars"] == len(context)
