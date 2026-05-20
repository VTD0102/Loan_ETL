"""Loan adjustment tool tests use monkeypatched ML and no external services."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import services.loan_adjustment_tool as tool


def _criterion_field(criterion):
    left = getattr(criterion, "left", None)
    return getattr(left, "key", None) or getattr(left, "name", None)


def _criterion_value(criterion):
    right = getattr(criterion, "right", None)
    return getattr(right, "value", None)


class FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, *args, **kwargs):
        for criterion in args:
            field = _criterion_field(criterion)
            value = _criterion_value(criterion)
            if field in {"id", "user_id", "status"}:
                self._items = [
                    item for item in self._items
                    if getattr(item, field, None) == value
                ]
        return self

    def order_by(self, *args, **kwargs):
        for criterion in args:
            element = getattr(criterion, "element", None)
            key = getattr(element, "key", None) or getattr(element, "name", None)
            if key == "submitted_at":
                self._items.sort(
                    key=lambda item: getattr(item, "submitted_at", datetime.min),
                    reverse=True,
                )
        return self

    def first(self):
        return self._items[0] if self._items else None


class FakeDB:
    def __init__(self, applications):
        self._applications = list(applications)

    def query(self, model):
        name = getattr(model, "__name__", None)
        if name == "LoanApplication":
            return FakeQuery(self._applications)
        return FakeQuery([])


def _rejected_app(**overrides):
    data = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "status": "AUTO_REJECTED",
        "monthly_income": Decimal("8000"),
        "loan_amount": Decimal("50000"),
        "term": 12,
        "employment_status": "Employed",
        "occupation_type": "Laborers",
        "years_employed": Decimal("5"),
        "dti": Decimal("0.35"),
        "is_homeowner": False,
        "listing_category": "personal",
        "credit_score": 680,
        "num_bureau_records": 3,
        "num_active_credit": 2,
        "total_overdue_amount": Decimal("0"),
        "max_credit_overdue_days": 0,
        "has_bad_debt": False,
        "income_verifiable_flag": True,
        "age_years": 35,
        "gender_male_flag": False,
        "education_ordinal": 4,
        "cnt_children": 0,
        "cnt_fam_members": 2,
        "is_married_flag": True,
        "recommended_amount": Decimal("35000"),
        "recommended_term": 36,
        "default_probability": Decimal("0.55"),
        "model_version": "test-model",
        "submitted_at": datetime.utcnow(),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _patch_tool(predictions, validation_failures=None):
    validation_failures = set(validation_failures or [])
    original_predict = tool.ml_service.predict
    original_load = tool.ml_service._load
    original_fetch_previous = tool.fetch_previous_applications
    original_validate = tool.validate_confirmed_values

    def fake_predict(payload, db=None, user_id=None):
        prob = predictions[(Decimal(str(payload.loan_amount)), int(payload.term))]
        return {
            "default_probability": prob,
            "risk_level": "High" if prob > 0.4 else "Medium",
            "risk_score": int(round((1 - prob) * 100)),
            "suggested_amount": 35000,
            "suggested_term": 36,
            "model_version": "test-model",
        }

    def fake_validate(payload, artifact, previous_applications=None):
        key = (Decimal(str(payload.loan_amount)), int(payload.term))
        if key in validation_failures:
            raise ValueError("candidate exceeds safe amount")

    tool.ml_service.predict = fake_predict
    tool.ml_service._load = lambda: {"thresholds": {"low": 0.2, "high": 0.4}}
    tool.fetch_previous_applications = lambda db, user_id: []
    tool.validate_confirmed_values = fake_validate

    def restore():
        tool.ml_service.predict = original_predict
        tool.ml_service._load = original_load
        tool.fetch_previous_applications = original_fetch_previous
        tool.validate_confirmed_values = original_validate

    return restore


def test_tool_selects_passing_term_at_original_amount():
    app = _rejected_app(recommended_amount=None)
    db = FakeDB([app])
    predictions = {
        (Decimal("50000"), 12): 0.55,
        (Decimal("50000"), 24): 0.45,
        (Decimal("50000"), 36): 0.32,
        (Decimal("50000"), 48): 0.34,
        (Decimal("50000"), 60): 0.38,
    }
    restore = _patch_tool(predictions)
    try:
        result = tool.find_best_reapplication_option(db, app.user_id)
    finally:
        restore()

    assert result.status == "proposal"
    assert result.source_application_id == str(app.id)
    assert result.proposal is not None
    assert result.proposal.loan_amount == Decimal("50000")
    assert result.proposal.term == 36
    assert result.proposal.default_probability == 0.32


def test_tool_falls_back_to_recommended_amount_when_original_amount_fails():
    app = _rejected_app()
    db = FakeDB([app])
    predictions = {
        (Decimal("50000"), 12): 0.55,
        (Decimal("50000"), 24): 0.52,
        (Decimal("50000"), 36): 0.50,
        (Decimal("50000"), 48): 0.49,
        (Decimal("50000"), 60): 0.48,
        (Decimal("35000"), 12): 0.43,
        (Decimal("35000"), 24): 0.41,
        (Decimal("35000"), 36): 0.28,
        (Decimal("35000"), 48): 0.30,
        (Decimal("35000"), 60): 0.35,
    }
    restore = _patch_tool(predictions)
    try:
        result = tool.find_best_reapplication_option(db, app.user_id)
    finally:
        restore()

    assert result.status == "proposal"
    assert result.proposal is not None
    assert result.proposal.loan_amount == Decimal("35000")
    assert result.proposal.term == 36
    assert result.proposal.default_probability == 0.28


def test_tool_skips_candidates_that_confirm_validation_would_reject():
    app = _rejected_app(recommended_amount=None)
    db = FakeDB([app])
    predictions = {
        (Decimal("50000"), 12): 0.55,
        (Decimal("50000"), 24): 0.45,
        (Decimal("50000"), 36): 0.30,
        (Decimal("50000"), 48): 0.31,
        (Decimal("50000"), 60): 0.39,
    }
    restore = _patch_tool(
        predictions,
        validation_failures={(Decimal("50000"), 36)},
    )
    try:
        result = tool.find_best_reapplication_option(db, app.user_id)
    finally:
        restore()

    assert result.status == "proposal"
    assert result.proposal is not None
    assert result.proposal.term == 48


def test_tool_uses_newest_same_user_auto_rejected_application():
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    newer_other_user = _rejected_app(
        user_id=other_user_id,
        loan_amount=Decimal("90000"),
        submitted_at=datetime(2026, 5, 19, 12, 0, 0),
    )
    same_user_non_rejected = _rejected_app(
        user_id=user_id,
        status="PENDING_REVIEW",
        loan_amount=Decimal("80000"),
        submitted_at=datetime(2026, 5, 19, 11, 0, 0),
    )
    older_same_user_rejected = _rejected_app(
        user_id=user_id,
        loan_amount=Decimal("70000"),
        submitted_at=datetime(2026, 5, 19, 10, 0, 0),
    )
    newer_same_user_rejected = _rejected_app(
        user_id=user_id,
        loan_amount=Decimal("60000"),
        submitted_at=datetime(2026, 5, 19, 10, 30, 0),
        recommended_amount=None,
    )
    db = FakeDB([
        newer_other_user,
        same_user_non_rejected,
        older_same_user_rejected,
        newer_same_user_rejected,
    ])
    predictions = {
        (Decimal("60000"), 12): 0.55,
        (Decimal("60000"), 24): 0.45,
        (Decimal("60000"), 36): 0.32,
        (Decimal("60000"), 48): 0.34,
        (Decimal("60000"), 60): 0.38,
    }
    restore = _patch_tool(predictions)
    try:
        result = tool.find_best_reapplication_option(db, user_id)
    finally:
        restore()

    assert result.status == "proposal"
    assert result.source_application_id == str(newer_same_user_rejected.id)
    assert result.current_loan_amount == Decimal("60000")
    assert result.proposal is not None
    assert result.proposal.loan_amount == Decimal("60000")


def test_tool_returns_no_proposal_for_cic_blacklist():
    app = _rejected_app(model_version="CIC_BLACKLIST")
    result = tool.find_best_reapplication_option(FakeDB([app]), app.user_id)

    assert result.status == "cic_blacklist"
    assert result.proposal is None


def test_tool_returns_no_rejected_application_status_when_missing():
    result = tool.find_best_reapplication_option(FakeDB([]), uuid.uuid4())

    assert result.status == "no_rejected_application"
    assert result.proposal is None


def test_tool_returns_no_passing_option_status_when_all_candidates_fail():
    app = _rejected_app(recommended_amount=None)
    db = FakeDB([app])
    predictions = {
        (Decimal("50000"), 12): 0.55,
        (Decimal("50000"), 24): 0.52,
        (Decimal("50000"), 36): 0.50,
        (Decimal("50000"), 48): 0.49,
        (Decimal("50000"), 60): 0.48,
    }
    restore = _patch_tool(predictions)
    try:
        result = tool.find_best_reapplication_option(db, app.user_id)
    finally:
        restore()

    assert result.status == "no_passing_option"
    assert result.proposal is None
    assert result.best_observed is not None


def test_get_source_application_returns_none_for_invalid_uuid():
    app = _rejected_app()

    result = tool.get_source_application(FakeDB([app]), app.user_id, "not-a-uuid")

    assert result is None


def test_get_source_application_returns_none_for_wrong_user():
    app = _rejected_app()

    result = tool.get_source_application(FakeDB([app]), uuid.uuid4(), app.id)

    assert result is None


def test_get_source_application_requires_auto_rejected_status():
    app = _rejected_app(status="PENDING_REVIEW")

    result = tool.get_source_application(FakeDB([app]), app.user_id, app.id)

    assert result is None


def test_pending_action_expiry_helpers():
    app = _rejected_app()
    proposal = tool.LoanAdjustmentProposal(
        loan_amount=Decimal("35000"),
        term=36,
        default_probability=0.28,
        risk_level="Medium",
        risk_score=72,
        model_version="test-model",
    )
    result = tool.LoanAdjustmentResult(
        status="proposal",
        source_application_id=str(app.id),
        current_loan_amount=app.loan_amount,
        current_term=app.term,
        current_default_probability=0.55,
        proposal=proposal,
        best_observed=None,
        message="proposal",
    )
    now = datetime(2026, 5, 19, 10, 0, 0)
    action = tool.build_pending_action(result, now=now)

    assert action["type"] == "loan_term_adjustment"
    assert action["status"] == "pending_confirmation"
    assert action["proposal"]["loan_amount"] == "35000"
    assert tool.is_pending_action_expired(action, now=now + timedelta(minutes=29)) is False
    assert tool.is_pending_action_expired(action, now=now + timedelta(minutes=30)) is True
    assert tool.is_pending_action_expired(action, now=now + timedelta(minutes=31)) is True


def test_build_pending_action_requires_proposal():
    result = tool.LoanAdjustmentResult(
        status="no_proposal",
        source_application_id=str(uuid.uuid4()),
        current_loan_amount=Decimal("50000"),
        current_term=12,
        current_default_probability=0.55,
        proposal=None,
        best_observed=None,
        message="No safe adjustment candidate was found.",
    )

    try:
        tool.build_pending_action(result)
    except ValueError as exc:
        assert "proposal" in str(exc)
    else:
        raise AssertionError("Expected ValueError for pending action without proposal")


def test_pending_action_expiry_accepts_timezone_aware_iso_strings():
    action = {
        "type": "loan_term_adjustment",
        "expires_at": "2026-05-19T10:30:00+00:00",
    }

    assert tool.is_pending_action_expired(
        action,
        now=datetime(2026, 5, 19, 10, 29, 0, tzinfo=timezone.utc),
    ) is False
    assert tool.is_pending_action_expired(
        action,
        now=datetime(2026, 5, 19, 10, 31, 0, tzinfo=timezone.utc),
    ) is True
    assert tool.is_pending_action_expired(
        action,
        now=datetime(2026, 5, 19, 10, 31, 0),
    ) is True


def test_application_to_confirm_payload_defaults_legacy_nullable_fields():
    app = _rejected_app(
        occupation_type=None,
        years_employed=None,
        num_bureau_records=None,
        num_active_credit=None,
        total_overdue_amount=None,
        max_credit_overdue_days=None,
        has_bad_debt=None,
        income_verifiable_flag=None,
        age_years=None,
        gender_male_flag=None,
        education_ordinal=None,
        cnt_children=None,
        cnt_fam_members=None,
        is_married_flag=None,
    )

    payload = tool.application_to_confirm_payload(
        app,
        loan_amount=Decimal("30000"),
        term=48,
    )

    assert payload.loan_amount == Decimal("30000")
    assert payload.term == 48
    assert payload.occupation_type == "Unknown"
    assert payload.years_employed == Decimal("0")
    assert payload.num_bureau_records == 0
    assert payload.num_active_credit == 0
    assert payload.total_overdue_amount == Decimal("0")
    assert payload.max_credit_overdue_days == 0
    assert payload.has_bad_debt is False
    assert payload.income_verifiable_flag is False
    assert payload.age_years == 30
    assert payload.gender_male_flag is False
    assert payload.education_ordinal == 3
    assert payload.cnt_children == 0
    assert payload.cnt_fam_members == 1
    assert payload.is_married_flag is False


if __name__ == "__main__":
    test_tool_selects_passing_term_at_original_amount()
    test_tool_falls_back_to_recommended_amount_when_original_amount_fails()
    test_tool_skips_candidates_that_confirm_validation_would_reject()
    test_tool_uses_newest_same_user_auto_rejected_application()
    test_tool_returns_no_proposal_for_cic_blacklist()
    test_tool_returns_no_rejected_application_status_when_missing()
    test_tool_returns_no_passing_option_status_when_all_candidates_fail()
    test_get_source_application_returns_none_for_invalid_uuid()
    test_get_source_application_returns_none_for_wrong_user()
    test_get_source_application_requires_auto_rejected_status()
    test_pending_action_expiry_helpers()
    test_build_pending_action_requires_proposal()
    test_pending_action_expiry_accepts_timezone_aware_iso_strings()
    test_application_to_confirm_payload_defaults_legacy_nullable_fields()
    print("loan adjustment tool tests passed")
