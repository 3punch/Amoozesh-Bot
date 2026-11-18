from __future__ import annotations

import pytest
from pydantic import ValidationError

from amoozesh_bot.models import BotResponse, Course, KnowledgeBase, ProfessorProfile


def test_course_normalizes_fields_and_eligible_inputs() -> None:
    course = Course(
        name="  ساختمان داده  ",
        instructor=" محمد همامی ",
        eligible_inputs="۱۴۰۳, ۱۴۰۴",
        raw={"source": "sheet"},
    )

    assert course.name == "ساختمان داده"
    assert course.instructor == "محمد همامی"
    assert course.eligible_inputs == ["۱۴۰۳", "۱۴۰۴"]
    assert course.raw["source"] == "sheet"


def test_course_rejects_blank_names_and_negative_capacity() -> None:
    with pytest.raises(ValidationError):
        Course(name="   ")
    with pytest.raises(ValidationError):
        Course(name="ریاضی", capacity=-1)


def test_profile_ignores_unrecognized_archive_fields() -> None:
    profile = ProfessorProfile(name="استاد نمونه", legacy_field="ignored")
    assert profile.name == "استاد نمونه"
    assert not hasattr(profile, "legacy_field")
    assert profile.comments == []


def test_knowledge_and_response_validate_user_facing_text() -> None:
    assert KnowledgeBase(rules="قوانین")
    with pytest.raises(ValidationError):
        KnowledgeBase(rules="")

    response = BotResponse(text="پاسخ", source="deep", metadata={"checked": True})
    assert response.metadata["checked"] is True
    with pytest.raises(ValidationError):
        BotResponse(text="")
