"""Verify build_personalization(user, app) works without db session."""
from types import SimpleNamespace
from rag.personalizer import build_personalization, PersonalizationContext


def test_no_user_no_app_returns_default():
    ctx = build_personalization(None, None)
    assert ctx.user_display_name == "Quý khách"
    assert ctx.application_status is None
    assert "THÂN THIỆN" in ctx.tone_instructions


def test_pending_review_tone():
    user = SimpleNamespace(username="Minh")
    app = SimpleNamespace(status="PENDING_REVIEW")
    ctx = build_personalization(user, app)
    assert ctx.user_display_name == "Minh"
    assert ctx.application_status == "pending_review"
    assert "KHÍCH LỆ" in ctx.tone_instructions


def test_auto_rejected_tone():
    user = SimpleNamespace(username="Lan")
    app = SimpleNamespace(status="AUTO_REJECTED")
    ctx = build_personalization(user, app)
    assert ctx.application_status == "auto_rejected"
    assert "ĐỒNG CẢM" in ctx.tone_instructions


def test_user_without_username():
    user = SimpleNamespace(username=None)
    ctx = build_personalization(user, None)
    assert ctx.user_display_name == "Quý khách"


if __name__ == "__main__":
    test_no_user_no_app_returns_default()
    test_pending_review_tone()
    test_auto_rejected_tone()
    test_user_without_username()
    print("personalization (no-db) tests passed")
