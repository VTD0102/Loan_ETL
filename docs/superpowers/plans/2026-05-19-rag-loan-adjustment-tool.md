# RAG Loan Adjustment Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the RAG chat flow propose a safer repayment term after `AUTO_REJECTED`, then create a new application through `application_service.confirm()` only after explicit user confirmation.

**Architecture:** Add a small deterministic loan adjustment tool in `backend/services/loan_adjustment_tool.py`. `chat_service.send()` orchestrates proposal and confirmation state through a `ChatSession.pending_action` JSON column while preserving the existing RAG path for normal messages.

**Tech Stack:** FastAPI service layer, SQLAlchemy models, Pydantic application schemas, local script-style tests under `backend/tests_local/`, existing ML service monkeypatching.

---

## File Structure

- Create `backend/services/loan_adjustment_tool.py`
  - Owns what-if simulation, candidate ranking, pending action shape, expiry checks, and formatting tool results for RAG context.
  - Does not write loan applications.
- Modify `backend/models/chat.py`
  - Add `ChatSession.pending_action` JSON column.
- Modify `backend/init_db.py`
  - Add idempotent `chat_sessions.pending_action` migration.
- Modify `backend/services/chat_service.py`
  - Detect adjustment intent.
  - Save pending action after proposal response.
  - Handle affirmative/negative response before normal RAG call.
  - Call `application_service.confirm()` only for explicit confirmation.
- Tests:
  - Create `backend/tests_local/test_chat_pending_action_schema.py`
  - Create `backend/tests_local/test_loan_adjustment_tool.py`
  - Create `backend/tests_local/test_chat_service_loan_adjustment.py`

Implementation note from current code: `application_service.confirm()` calls `validate_confirmed_values()` before prediction, so the tool must only return proposals that pass the same validation path. A candidate with `default_probability <= 0.4` is not enough if it fails the safe-amount validation.

---

## Task 1: Add ChatSession Pending Action State

**Files:**
- Modify: `backend/models/chat.py`
- Modify: `backend/init_db.py`
- Test: `backend/tests_local/test_chat_pending_action_schema.py`

- [ ] **Step 1: Write the failing schema test**

Create `backend/tests_local/test_chat_pending_action_schema.py`:

```python
"""Verify chat sessions can store pending conversational actions."""

from init_db import _COLUMN_MIGRATIONS
from models.chat import ChatSession


def test_chat_session_has_pending_action_json_column():
    column = ChatSession.__table__.columns["pending_action"]
    assert column.nullable is True
    assert "JSON" in column.type.__class__.__name__.upper()


def test_init_db_registers_pending_action_migration():
    migration_sql = "\n".join(_COLUMN_MIGRATIONS).lower()
    assert "alter table chat_sessions add column if not exists pending_action" in migration_sql
    assert "jsonb" in migration_sql


if __name__ == "__main__":
    test_chat_session_has_pending_action_json_column()
    test_init_db_registers_pending_action_migration()
    print("chat pending action schema tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_pending_action_schema.py
```

Expected: FAIL with `KeyError: 'pending_action'`.

- [ ] **Step 3: Add model column and migration**

In `backend/models/chat.py`, update imports:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
```

In `ChatSession`, add the column below `summary_updated_at`:

```python
    pending_action: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

In `backend/init_db.py`, append this string to `_COLUMN_MIGRATIONS` after the existing `chat_sessions` summary migrations:

```python
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS pending_action JSONB",
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_pending_action_schema.py
```

Expected: `chat pending action schema tests passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/models/chat.py backend/init_db.py backend/tests_local/test_chat_pending_action_schema.py
git commit -m "feat: add chat pending action state"
```

---

## Task 2: Add Loan Adjustment What-If Tool

**Files:**
- Create: `backend/services/loan_adjustment_tool.py`
- Test: `backend/tests_local/test_loan_adjustment_tool.py`

- [ ] **Step 1: Write failing tool tests**

Create `backend/tests_local/test_loan_adjustment_tool.py`:

```python
"""Loan adjustment tool tests use monkeypatched ML and no external services."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import services.loan_adjustment_tool as tool


class FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
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


def test_tool_returns_no_proposal_for_cic_blacklist():
    app = _rejected_app(model_version="CIC_BLACKLIST")
    result = tool.find_best_reapplication_option(FakeDB([app]), app.user_id)

    assert result.status == "cic_blacklist"
    assert result.proposal is None


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
    assert action["proposal"]["loan_amount"] == "35000"
    assert tool.is_pending_action_expired(action, now=now + timedelta(minutes=29)) is False
    assert tool.is_pending_action_expired(action, now=now + timedelta(minutes=31)) is True


if __name__ == "__main__":
    test_tool_selects_passing_term_at_original_amount()
    test_tool_falls_back_to_recommended_amount_when_original_amount_fails()
    test_tool_skips_candidates_that_confirm_validation_would_reject()
    test_tool_returns_no_proposal_for_cic_blacklist()
    test_pending_action_expiry_helpers()
    print("loan adjustment tool tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_loan_adjustment_tool.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'services.loan_adjustment_tool'`.

- [ ] **Step 3: Implement the tool**

Create `backend/services/loan_adjustment_tool.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from models.application import LoanApplication
from schemas.application import ApplicationConfirm
from services import ml_service
from services.loan_suggestion_service import validate_confirmed_values
from services.model_feature_builder import fetch_previous_applications


SUPPORTED_TERMS = (12, 24, 36, 48, 60)
AUTO_REVIEW_THRESHOLD = 0.4
PENDING_ACTION_TTL_MINUTES = 30


@dataclass(frozen=True)
class LoanAdjustmentProposal:
    loan_amount: Decimal
    term: int
    default_probability: float
    risk_level: str
    risk_score: int
    model_version: str | None


@dataclass(frozen=True)
class LoanAdjustmentResult:
    status: Literal[
        "proposal",
        "no_rejected_application",
        "cic_blacklist",
        "no_passing_option",
    ]
    source_application_id: str | None
    current_loan_amount: Decimal | None
    current_term: int | None
    current_default_probability: float | None
    proposal: LoanAdjustmentProposal | None
    best_observed: LoanAdjustmentProposal | None
    message: str


def find_best_reapplication_option(db: Session, user_id: Any) -> LoanAdjustmentResult:
    """Find a confirm-safe reapplication proposal for the latest AUTO_REJECTED app."""
    app = _latest_auto_rejected_application(db, user_id)
    if app is None:
        return LoanAdjustmentResult(
            status="no_rejected_application",
            source_application_id=None,
            current_loan_amount=None,
            current_term=None,
            current_default_probability=None,
            proposal=None,
            best_observed=None,
            message="Không tìm thấy hồ sơ bị từ chối tự động để mô phỏng.",
        )

    if app.model_version == "CIC_BLACKLIST":
        return LoanAdjustmentResult(
            status="cic_blacklist",
            source_application_id=str(app.id),
            current_loan_amount=app.loan_amount,
            current_term=app.term,
            current_default_probability=_float_or_none(app.default_probability),
            proposal=None,
            best_observed=None,
            message="Hồ sơ bị từ chối do danh sách đen CIC; đổi kỳ hạn không xử lý được lý do này.",
        )

    candidates = _candidate_amounts(app)
    artifact = ml_service._load()
    previous = fetch_previous_applications(db, user_id)

    passing: list[tuple[int, int, LoanAdjustmentProposal]] = []
    observed: list[LoanAdjustmentProposal] = []

    for amount_index, amount in enumerate(candidates):
        for term in SUPPORTED_TERMS:
            payload = application_to_confirm_payload(app, loan_amount=amount, term=term)
            prediction = ml_service.predict(payload, db=db, user_id=user_id)
            proposal = _proposal_from_prediction(payload, prediction)
            observed.append(proposal)
            if proposal.default_probability > AUTO_REVIEW_THRESHOLD:
                continue
            try:
                validate_confirmed_values(payload, artifact, previous_applications=previous)
            except ValueError:
                continue
            distance = abs(int(term) - int(app.term))
            passing.append((amount_index, distance, proposal))

    if passing:
        passing.sort(key=lambda item: (item[0], item[2].default_probability, item[1], item[2].term))
        proposal = passing[0][2]
        return LoanAdjustmentResult(
            status="proposal",
            source_application_id=str(app.id),
            current_loan_amount=app.loan_amount,
            current_term=app.term,
            current_default_probability=_float_or_none(app.default_probability),
            proposal=proposal,
            best_observed=None,
            message="Tìm thấy phương án nộp lại có thể qua vòng sàng lọc tự động.",
        )

    best_observed = min(observed, key=lambda item: item.default_probability) if observed else None
    return LoanAdjustmentResult(
        status="no_passing_option",
        source_application_id=str(app.id),
        current_loan_amount=app.loan_amount,
        current_term=app.term,
        current_default_probability=_float_or_none(app.default_probability),
        proposal=None,
        best_observed=best_observed,
        message="Các kỳ hạn và mức tiền đã thử vẫn chưa đủ điều kiện qua vòng sàng lọc tự động.",
    )


def get_source_application(db: Session, user_id: Any, source_application_id: str) -> LoanApplication | None:
    try:
        app_id = UUID(str(source_application_id))
    except ValueError:
        return None
    return (
        db.query(LoanApplication)
        .filter(
            LoanApplication.id == app_id,
            LoanApplication.user_id == user_id,
            LoanApplication.status == "AUTO_REJECTED",
        )
        .first()
    )


def application_to_confirm_payload(
    app: LoanApplication,
    loan_amount: Decimal | None = None,
    term: int | None = None,
) -> ApplicationConfirm:
    """Rebuild a confirm payload from a stored application row."""
    return ApplicationConfirm.model_construct(
        monthly_income=app.monthly_income,
        loan_amount=loan_amount if loan_amount is not None else app.loan_amount,
        term=term if term is not None else app.term,
        employment_status=app.employment_status,
        occupation_type=app.occupation_type or "Unknown",
        years_employed=app.years_employed or Decimal("0"),
        dti=app.dti,
        is_homeowner=app.is_homeowner,
        listing_category=app.listing_category,
        credit_score=app.credit_score,
        num_bureau_records=app.num_bureau_records or 0,
        num_active_credit=app.num_active_credit or 0,
        total_overdue_amount=app.total_overdue_amount or Decimal("0"),
        max_credit_overdue_days=app.max_credit_overdue_days or 0,
        has_bad_debt=app.has_bad_debt or False,
        income_verifiable_flag=app.income_verifiable_flag or False,
        age_years=app.age_years or 30,
        gender_male_flag=app.gender_male_flag or False,
        education_ordinal=app.education_ordinal or 3,
        cnt_children=app.cnt_children or 0,
        cnt_fam_members=app.cnt_fam_members or 1,
        is_married_flag=app.is_married_flag or False,
    )


def build_pending_action(result: LoanAdjustmentResult, now: datetime | None = None) -> dict[str, Any]:
    if result.proposal is None or result.source_application_id is None:
        raise ValueError("pending action requires a proposal and source application")
    timestamp = now or datetime.utcnow()
    expires_at = timestamp + timedelta(minutes=PENDING_ACTION_TTL_MINUTES)
    proposal = result.proposal
    return {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": result.source_application_id,
        "proposal": {
            "loan_amount": str(proposal.loan_amount),
            "term": proposal.term,
            "default_probability": proposal.default_probability,
            "risk_level": proposal.risk_level,
            "risk_score": proposal.risk_score,
            "model_version": proposal.model_version,
        },
        "created_at": timestamp.isoformat(),
        "expires_at": expires_at.isoformat(),
    }


def is_pending_action_expired(action: dict[str, Any], now: datetime | None = None) -> bool:
    expires_at = action.get("expires_at")
    if not expires_at:
        return True
    try:
        expires = datetime.fromisoformat(str(expires_at))
    except ValueError:
        return True
    return (now or datetime.utcnow()) >= expires


def format_result_for_rag(result: LoanAdjustmentResult) -> str:
    lines = [
        "Kết quả tool mô phỏng điều chỉnh khoản vay:",
        f"- Trạng thái tool: {result.status}",
        f"- Thông điệp: {result.message}",
    ]
    if result.current_loan_amount is not None and result.current_term is not None:
        lines.append(f"- Hồ sơ hiện tại: {result.current_loan_amount} trong {result.current_term} tháng")
    if result.current_default_probability is not None:
        lines.append(f"- Xác suất vỡ nợ hiện tại: {result.current_default_probability:.4f}")
    if result.proposal is not None:
        lines.extend([
            "- Phương án đề xuất:",
            f"  - Số tiền vay: {result.proposal.loan_amount}",
            f"  - Kỳ hạn: {result.proposal.term} tháng",
            f"  - Xác suất vỡ nợ dự kiến: {result.proposal.default_probability:.4f}",
            f"  - Mức rủi ro: {result.proposal.risk_level}",
            "  - Trạng thái dự kiến nếu nộp: PENDING_REVIEW",
            "- Bắt buộc hỏi user xác nhận trước khi nộp lại.",
        ])
    if result.best_observed is not None:
        lines.extend([
            "- Phương án tốt nhất quan sát được nhưng chưa đạt điều kiện:",
            f"  - Số tiền vay: {result.best_observed.loan_amount}",
            f"  - Kỳ hạn: {result.best_observed.term} tháng",
            f"  - Xác suất vỡ nợ: {result.best_observed.default_probability:.4f}",
        ])
    lines.append("- Không được hứa chắc chắn được duyệt cuối cùng.")
    return "\n".join(lines)


def _latest_auto_rejected_application(db: Session, user_id: Any) -> LoanApplication | None:
    return (
        db.query(LoanApplication)
        .filter(
            LoanApplication.user_id == user_id,
            LoanApplication.status == "AUTO_REJECTED",
        )
        .order_by(LoanApplication.submitted_at.desc())
        .first()
    )


def _candidate_amounts(app: LoanApplication) -> list[Decimal]:
    amounts = [Decimal(str(app.loan_amount))]
    recommended = app.recommended_amount
    if recommended is not None and Decimal(str(recommended)) > 0:
        normalized = Decimal(str(recommended))
        if normalized not in amounts:
            amounts.append(normalized)
    return amounts


def _proposal_from_prediction(payload: ApplicationConfirm, prediction: dict[str, Any]) -> LoanAdjustmentProposal:
    return LoanAdjustmentProposal(
        loan_amount=Decimal(str(payload.loan_amount)),
        term=int(payload.term),
        default_probability=float(prediction["default_probability"]),
        risk_level=str(prediction["risk_level"]),
        risk_score=int(prediction["risk_score"]),
        model_version=prediction.get("model_version"),
    )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_loan_adjustment_tool.py
```

Expected: `loan adjustment tool tests passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/services/loan_adjustment_tool.py backend/tests_local/test_loan_adjustment_tool.py
git commit -m "feat: add loan adjustment what-if tool"
```

---

## Task 3: Wire Proposal Path Into Chat Service

**Files:**
- Modify: `backend/services/chat_service.py`
- Test: `backend/tests_local/test_chat_service_loan_adjustment.py`

- [ ] **Step 1: Write failing proposal-path test**

Create `backend/tests_local/test_chat_service_loan_adjustment.py`:

```python
"""Chat service orchestration for loan adjustment proposals and confirmation."""

import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import services.chat_service as chat_service
from models.chat import ChatMessage, ChatSession
from services.loan_adjustment_tool import LoanAdjustmentProposal, LoanAdjustmentResult


class FakeQuery:
    def __init__(self, items, scalar_value=0):
        self._items = list(items)
        self._scalar_value = scalar_value

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def scalar(self):
        return self._scalar_value

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, user, session=None, applications=None, messages=None):
        self._user = user
        self._session = session
        self._applications = list(applications or [])
        self._messages = list(messages or [])
        self.added = []
        self.committed = 0

    def query(self, model):
        name = getattr(model, "__name__", None)
        if name == "User":
            return FakeQuery([self._user])
        if name == "LoanApplication":
            return FakeQuery(self._applications)
        if name == "ChatSession":
            return FakeQuery([self._session] if self._session is not None else [])
        if name == "ChatMessage":
            return FakeQuery(self._messages)
        return FakeQuery([])

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, ChatSession) and getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
            self._session = obj
        if isinstance(obj, ChatMessage):
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "created_at", None) is None:
                obj.created_at = datetime.utcnow()
            self._messages.append(obj)

    def flush(self):
        if self._session is not None and getattr(self._session, "id", None) is None:
            self._session.id = uuid.uuid4()

    def commit(self):
        self.committed += 1

    def rollback(self):
        pass


def _session(user_id=None, pending_action=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        title="chat",
        summary=None,
        summary_covers_until_id=None,
        summary_updated_at=None,
        pending_action=pending_action,
        updated_at=None,
    )


def _proposal_result(source_application_id):
    return LoanAdjustmentResult(
        status="proposal",
        source_application_id=str(source_application_id),
        current_loan_amount=Decimal("50000"),
        current_term=12,
        current_default_probability=0.55,
        proposal=LoanAdjustmentProposal(
            loan_amount=Decimal("35000"),
            term=36,
            default_probability=0.28,
            risk_level="Medium",
            risk_score=72,
            model_version="test-model",
        ),
        best_observed=None,
        message="proposal",
    )


def _patch_common(rag_answer="Đề xuất kỳ hạn 36 tháng. Bạn có muốn nộp lại với phương án này không?"):
    originals = {
        "rag": chat_service._rag_invoke,
        "ctx": chat_service.build_user_context,
        "memory": chat_service.load_memory,
        "personalization": chat_service.build_personalization,
    }
    rag_calls = []

    def fake_rag(question, context, chat_history, **kwargs):
        rag_calls.append({"question": question, "context": context, "kwargs": kwargs})
        return {"answer": rag_answer, "source_documents": []}

    def fake_memory(db, session, exclude_message_id=None):
        from rag.memory import MemoryContext

        return MemoryContext(summary=None, recent_messages=[])

    chat_service._rag_invoke = fake_rag
    chat_service.build_user_context = lambda db, user_id: "base user context"
    chat_service.load_memory = fake_memory
    chat_service.build_personalization = lambda user, app: None

    def restore():
        chat_service._rag_invoke = originals["rag"]
        chat_service.build_user_context = originals["ctx"]
        chat_service.load_memory = originals["memory"]
        chat_service.build_personalization = originals["personalization"]

    return rag_calls, restore


def test_adjustment_question_stores_pending_action_without_submitting():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    source_application_id = uuid.uuid4()
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common()

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    original_build = chat_service.loan_adjustment_tool.build_pending_action
    chat_service.loan_adjustment_tool.find_best_reapplication_option = (
        lambda db, user_id: _proposal_result(source_application_id)
    )
    chat_service.loan_adjustment_tool.build_pending_action = lambda result: {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": result.source_application_id,
        "proposal": {
            "loan_amount": "35000",
            "term": 36,
            "default_probability": 0.28,
            "risk_level": "Medium",
            "risk_score": 72,
            "model_version": "test-model",
        },
        "created_at": "2026-05-19T10:00:00",
        "expires_at": "2026-05-19T10:30:00",
    }
    chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)

    try:
        result = chat_service.send(
            db,
            "loan@example.com",
            "Tôi bị từ chối, đổi kỳ hạn nào để dễ được duyệt hơn?",
            session_id=session.id,
        )
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        chat_service.loan_adjustment_tool.build_pending_action = original_build
        restore_common()

    assert result["response"].startswith("Đề xuất kỳ hạn 36 tháng")
    assert session.pending_action is not None
    assert session.pending_action["type"] == "loan_term_adjustment"
    assert session.pending_action["proposal"]["term"] == 36
    assert len(rag_calls) == 1
    assert "Kết quả tool mô phỏng điều chỉnh khoản vay" in rag_calls[0]["context"]
    assistant_messages = [m for m in db.added if isinstance(m, ChatMessage) and m.role == "assistant"]
    assert len(assistant_messages) == 1
    assert db.committed >= 2


def test_adjustment_question_without_proposal_does_not_store_pending_action():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common(rag_answer="Chưa có phương án đủ điều kiện.")

    no_proposal = LoanAdjustmentResult(
        status="no_passing_option",
        source_application_id=str(uuid.uuid4()),
        current_loan_amount=Decimal("50000"),
        current_term=12,
        current_default_probability=0.55,
        proposal=None,
        best_observed=LoanAdjustmentProposal(
            loan_amount=Decimal("35000"),
            term=36,
            default_probability=0.43,
            risk_level="High",
            risk_score=57,
            model_version="test-model",
        ),
        message="no proposal",
    )

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    original_build = chat_service.loan_adjustment_tool.build_pending_action
    build_calls = []
    chat_service.loan_adjustment_tool.find_best_reapplication_option = lambda db, user_id: no_proposal
    chat_service.loan_adjustment_tool.build_pending_action = lambda result: build_calls.append(result)
    try:
        result = chat_service.send(
            db,
            "loan@example.com",
            "Tôi bị từ chối, đổi kỳ hạn giúp tôi",
            session_id=session.id,
        )
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        chat_service.loan_adjustment_tool.build_pending_action = original_build
        restore_common()

    assert result["response"] == "Chưa có phương án đủ điều kiện."
    assert session.pending_action is None
    assert build_calls == []
    assert len(rag_calls) == 1
    assert "Phương án tốt nhất quan sát được" in rag_calls[0]["context"]


if __name__ == "__main__":
    test_adjustment_question_stores_pending_action_without_submitting()
    test_adjustment_question_without_proposal_does_not_store_pending_action()
    print("chat service loan adjustment tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_loan_adjustment.py
```

Expected: FAIL with `AttributeError` for missing `loan_adjustment_tool` on `services.chat_service`.

- [ ] **Step 3: Implement proposal-path orchestration**

Update service imports near `ml_service`:

```python
from services import loan_adjustment_tool, ml_service
```

Add constants below `_RAG_ERROR_MESSAGE`:

```python
_ADJUSTMENT_INTENT_KEYWORDS = (
    "bị từ chối",
    "bi tu choi",
    "không được duyệt",
    "khong duoc duyet",
    "đổi kỳ hạn",
    "doi ky han",
    "đổi thời hạn",
    "doi thoi han",
    "nộp lại",
    "nop lai",
    "tăng khả năng",
    "tang kha nang",
    "dễ được duyệt",
    "de duoc duyet",
)
```

In the `try:` block before `context = build_user_context(db, user.id)`, add:

```python
        tool_result = None
        pending_action = None
        if _is_loan_adjustment_request(payload_message):
            tool_result = loan_adjustment_tool.find_best_reapplication_option(db, user.id)
            if tool_result.proposal is not None:
                pending_action = loan_adjustment_tool.build_pending_action(tool_result)
```

Replace:

```python
        context = build_user_context(db, user.id)
```

with:

```python
        context = build_user_context(db, user.id)
        if tool_result is not None:
            context = f"{context}\n\n{loan_adjustment_tool.format_result_for_rag(tool_result)}"
```

After:

```python
        if not answer:
            answer = _RAG_ERROR_MESSAGE
            error_flag = True
            sources = []
```

add:

```python
        if pending_action is not None and not error_flag:
            session.pending_action = pending_action
```

Add helper functions near the bottom of `backend/services/chat_service.py`, above `_extract_sources`:

```python
def _is_loan_adjustment_request(message: str) -> bool:
    text = _normalize_message(message)
    return any(keyword in text for keyword in _ADJUSTMENT_INTENT_KEYWORDS)


def _normalize_message(message: str) -> str:
    return " ".join(str(message).strip().lower().split())
```

- [ ] **Step 4: Run proposal test to verify it passes**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_loan_adjustment.py
```

Expected: `chat service loan adjustment tests passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/services/chat_service.py backend/tests_local/test_chat_service_loan_adjustment.py
git commit -m "feat: wire loan adjustment proposal into chat"
```

---

## Task 4: Add Confirmation, Cancellation, and Expiry Tests

**Files:**
- Modify: `backend/tests_local/test_chat_service_loan_adjustment.py`
- Modify: `backend/services/chat_service.py`

- [ ] **Step 1: Add failing orchestration tests**

Append these tests to `backend/tests_local/test_chat_service_loan_adjustment.py`, above the `if __name__ == "__main__":` block:

```python
def _source_app(app_id, user_id):
    return SimpleNamespace(
        id=app_id,
        user_id=user_id,
        status="AUTO_REJECTED",
        monthly_income=Decimal("8000"),
        loan_amount=Decimal("50000"),
        term=12,
        employment_status="Employed",
        occupation_type="Laborers",
        years_employed=Decimal("5"),
        dti=Decimal("0.35"),
        is_homeowner=False,
        listing_category="personal",
        credit_score=680,
        num_bureau_records=3,
        num_active_credit=2,
        total_overdue_amount=Decimal("0"),
        max_credit_overdue_days=0,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=35,
        gender_male_flag=False,
        education_ordinal=4,
        cnt_children=0,
        cnt_fam_members=2,
        is_married_flag=True,
        recommended_amount=Decimal("35000"),
        recommended_term=36,
        default_probability=Decimal("0.55"),
        risk_level="High",
        risk_score=45,
        model_version="test-model",
        feature_snapshot={},
        imputed_features=[],
    )


def _pending_action(app_id):
    return {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": str(app_id),
        "proposal": {
            "loan_amount": "35000",
            "term": 36,
            "default_probability": 0.28,
            "risk_level": "Medium",
            "risk_score": 72,
            "model_version": "test-model",
        },
        "created_at": "2026-05-19T10:00:00",
        "expires_at": "2099-05-19T10:30:00",
    }


def test_affirmative_response_confirms_pending_action_and_clears_it():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    session = _session(user.id, pending_action=_pending_action(app_id))
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common()

    original_confirm = chat_service.application_service.confirm
    confirm_payloads = []

    def fake_confirm(db, user_email, payload):
        confirm_payloads.append(payload)
        return {
            "application_id": str(uuid.uuid4()),
            "status": "PENDING_REVIEW",
            "default_probability": 0.28,
            "risk_level": "Medium",
            "risk_score": 72,
            "suggested_amount": 35000,
            "suggested_term": 36,
        }

    chat_service.application_service.confirm = fake_confirm
    try:
        result = chat_service.send(db, "loan@example.com", "đồng ý nộp lại", session_id=session.id)
    finally:
        chat_service.application_service.confirm = original_confirm
        restore_common()

    assert "Đã nộp lại hồ sơ mới" in result["response"]
    assert session.pending_action is None
    assert len(confirm_payloads) == 1
    assert confirm_payloads[0].loan_amount == Decimal("35000")
    assert confirm_payloads[0].term == 36
    assert rag_calls == []


def test_negative_response_clears_pending_action_without_confirming():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    session = _session(user.id, pending_action=_pending_action(app_id))
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common()

    original_confirm = chat_service.application_service.confirm
    confirm_calls = []
    chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)
    try:
        result = chat_service.send(db, "loan@example.com", "không, hủy giúp tôi", session_id=session.id)
    finally:
        chat_service.application_service.confirm = original_confirm
        restore_common()

    assert "đã hủy" in result["response"].lower()
    assert session.pending_action is None
    assert confirm_calls == []
    assert rag_calls == []


def test_expired_pending_action_clears_without_confirming():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    app_id = uuid.uuid4()
    action = _pending_action(app_id)
    action["expires_at"] = "2000-01-01T00:00:00"
    session = _session(user.id, pending_action=action)
    db = FakeDB(user, session=session, applications=[_source_app(app_id, user.id)])
    rag_calls, restore_common = _patch_common()

    original_confirm = chat_service.application_service.confirm
    confirm_calls = []
    chat_service.application_service.confirm = lambda *args, **kwargs: confirm_calls.append(args)
    try:
        result = chat_service.send(db, "loan@example.com", "đồng ý", session_id=session.id)
    finally:
        chat_service.application_service.confirm = original_confirm
        restore_common()

    assert "hết hạn" in result["response"].lower()
    assert session.pending_action is None
    assert confirm_calls == []
    assert rag_calls == []


def test_non_adjustment_message_keeps_existing_rag_path():
    user = SimpleNamespace(id=uuid.uuid4(), email="loan@example.com", username="Lan")
    session = _session(user.id)
    db = FakeDB(user, session=session)
    rag_calls, restore_common = _patch_common(rag_answer="Câu trả lời RAG bình thường")

    original_find = chat_service.loan_adjustment_tool.find_best_reapplication_option
    find_calls = []
    chat_service.loan_adjustment_tool.find_best_reapplication_option = lambda *args, **kwargs: find_calls.append(args)
    try:
        result = chat_service.send(db, "loan@example.com", "DTI là gì?", session_id=session.id)
    finally:
        chat_service.loan_adjustment_tool.find_best_reapplication_option = original_find
        restore_common()

    assert result["response"] == "Câu trả lời RAG bình thường"
    assert session.pending_action is None
    assert find_calls == []
    assert len(rag_calls) == 1
```

Replace the `if __name__ == "__main__":` block with:

```python
if __name__ == "__main__":
    test_adjustment_question_stores_pending_action_without_submitting()
    test_affirmative_response_confirms_pending_action_and_clears_it()
    test_negative_response_clears_pending_action_without_confirming()
    test_expired_pending_action_clears_without_confirming()
    test_non_adjustment_message_keeps_existing_rag_path()
    print("chat service loan adjustment tests passed")
```

- [ ] **Step 2: Run test to verify failures**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_loan_adjustment.py
```

Expected: FAIL with `AttributeError: module 'services.chat_service' has no attribute 'application_service'`.

- [ ] **Step 3: Complete chat service branches**

In `backend/services/chat_service.py`, import `Decimal`:

```python
from decimal import Decimal
```

Update service imports:

```python
from services import application_service, loan_adjustment_tool, ml_service
```

Add constants below `_ADJUSTMENT_INTENT_KEYWORDS`:

```python
_AFFIRMATIVE_KEYWORDS = (
    "đồng ý",
    "dong y",
    "xác nhận",
    "xac nhan",
    "nộp lại",
    "nop lai",
    "gửi lại",
    "gui lai",
    "ok",
    "duyệt phương án",
    "duyet phuong an",
)

_NEGATIVE_KEYWORDS = (
    "không",
    "khong",
    "hủy",
    "huy",
    "bỏ qua",
    "bo qua",
    "đổi phương án khác",
    "doi phuong an khac",
)
```

Ensure `_handle_pending_loan_adjustment_response()` is called before tool proposal detection and before the normal RAG call:

```python
    direct_answer = _handle_pending_loan_adjustment_response(db, user_email, user.id, session, payload_message)
    if direct_answer is not None:
        db.add(ChatMessage(
            session_id=session.id,
            role="assistant",
            content=direct_answer,
            sources=[],
            error=False,
        ))
        session.updated_at = datetime.utcnow()
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist assistant message")
            raise HTTPException(503, _RAG_ERROR_MESSAGE)
        return {
            "response": direct_answer,
            "session_id": session.id,
            "sources": [],
        }
```

Add helper functions above `_is_loan_adjustment_request()`:

```python
def _handle_pending_loan_adjustment_response(
    db: Session,
    user_email: str,
    user_id: Any,
    session: ChatSession,
    message: str,
) -> str | None:
    action = getattr(session, "pending_action", None) or {}
    if action.get("type") != "loan_term_adjustment":
        return None
    if action.get("status") != "pending_confirmation":
        return None

    if _is_negative_response(message):
        session.pending_action = None
        return "Mình đã hủy phương án nộp lại đang chờ xác nhận. Hồ sơ bị từ chối cũ không bị thay đổi."

    if not _is_affirmative_response(message):
        return None

    if loan_adjustment_tool.is_pending_action_expired(action):
        session.pending_action = None
        return "Phương án nộp lại đã hết hạn. Bạn hãy yêu cầu mình mô phỏng lại để lấy kết quả mới nhất."

    return _confirm_pending_loan_adjustment(db, user_email, user_id, session, action)


def _confirm_pending_loan_adjustment(
    db: Session,
    user_email: str,
    user_id: Any,
    session: ChatSession,
    action: dict[str, Any],
) -> str:
    source_application_id = str(action.get("source_application_id") or "")
    source_app = loan_adjustment_tool.get_source_application(db, user_id, source_application_id)
    if source_app is None:
        session.pending_action = None
        return "Không tìm thấy hồ sơ gốc của phương án này. Mình đã hủy phương án cũ; bạn hãy yêu cầu mô phỏng lại."

    proposal = action.get("proposal") or {}
    payload = loan_adjustment_tool.application_to_confirm_payload(
        source_app,
        loan_amount=Decimal(str(proposal["loan_amount"])),
        term=int(proposal["term"]),
    )

    try:
        result = application_service.confirm(db, user_email, payload)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_503_SERVICE_UNAVAILABLE:
            session.pending_action = None
        return f"Chưa thể nộp lại phương án này: {exc.detail}"

    session.pending_action = None
    return (
        "Đã nộp lại hồ sơ mới với "
        f"số tiền {payload.loan_amount} và kỳ hạn {payload.term} tháng. "
        f"Mã hồ sơ mới: {result['application_id']}. "
        f"Trạng thái hiện tại: {result['status']}. "
        f"Xác suất vỡ nợ dự kiến: {float(result['default_probability']):.4f}. "
        "Hồ sơ bị từ chối trước đó không bị chỉnh sửa."
    )


def _is_affirmative_response(message: str) -> bool:
    text = _normalize_message(message)
    if any(keyword in text for keyword in _NEGATIVE_KEYWORDS):
        return False
    return any(keyword in text for keyword in _AFFIRMATIVE_KEYWORDS)


def _is_negative_response(message: str) -> bool:
    text = _normalize_message(message)
    return any(keyword in text for keyword in _NEGATIVE_KEYWORDS)
```

Ensure `_confirm_pending_loan_adjustment()` uses the stored proposal and clears pending action on success:

```python
    session.pending_action = None
    return (
        "Đã nộp lại hồ sơ mới với "
        f"số tiền {payload.loan_amount} và kỳ hạn {payload.term} tháng. "
        f"Mã hồ sơ mới: {result['application_id']}. "
        f"Trạng thái hiện tại: {result['status']}. "
        f"Xác suất vỡ nợ dự kiến: {float(result['default_probability']):.4f}. "
        "Hồ sơ bị từ chối trước đó không bị chỉnh sửa."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_loan_adjustment.py
```

Expected: `chat service loan adjustment tests passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/services/chat_service.py backend/tests_local/test_chat_service_loan_adjustment.py
git commit -m "feat: confirm loan adjustment from chat"
```

---

## Task 5: Focused Regression Sweep

**Files:**
- No source edits expected.

- [ ] **Step 1: Run new tests**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_pending_action_schema.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_loan_adjustment_tool.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_loan_adjustment.py
```

Expected:

```text
chat pending action schema tests passed
loan adjustment tool tests passed
chat service loan adjustment tests passed
```

- [ ] **Step 2: Run existing affected tests**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_atomic_save.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_excludes_current_user_message.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_service_uses_memory.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_chat_legacy_application_payload.py
PYTHONPATH=. ../.venv/bin/python tests_local/test_application_terms.py
```

Expected:

```text
chat_service atomic save test passed
chat_service excludes-current-user-message test passed
chat_service uses memory test passed
Legacy chat application payload test passed
application term tests passed
```

- [ ] **Step 3: Run non-live RAG/chat/memory sweep**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL/backend
SKIP=(
  tests_local/test_rag_benchmark.py
  tests_local/test_rag_evaluation_notebook.py
)
for f in tests_local/test_rag_*.py tests_local/test_chat_*.py tests_local/test_memory_*.py; do
    skip=false
    for s in "${SKIP[@]}"; do
        [[ "$f" == "$s" ]] && skip=true && break
    done
    [[ "$skip" == true ]] && { echo "=== $f === SKIPPED (live)"; continue; }
    echo "=== $f ==="
    PYTHONPATH=. ../.venv/bin/python "$f" || { echo "FAIL: $f"; exit 1; }
done
echo "All non-live tests passed"
```

Expected: `All non-live tests passed`.

- [ ] **Step 4: Commit if any sweep-only fixes were required**

If no files changed, do not commit. If a small compatibility fix was required by the sweep, commit only that fix:

```bash
git add backend/services/chat_service.py backend/services/loan_adjustment_tool.py backend/tests_local/test_chat_service_loan_adjustment.py
git commit -m "fix: stabilize loan adjustment chat flow"
```

---

## Task 6: Final Verification and Status

**Files:**
- No source edits expected.

- [ ] **Step 1: Check git status**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL
git status --short --branch
```

Expected: clean worktree on branch `taitu`, ahead by the new local commits.

- [ ] **Step 2: List commits for the feature**

Run:

```bash
cd /home/taitu/GitHub/Loan_ETL
git log --oneline -8
```

Expected: includes these titles in order:

```text
feat: add chat pending action state
feat: add loan adjustment what-if tool
feat: wire loan adjustment proposal into chat
feat: confirm loan adjustment from chat
```

- [ ] **Step 3: Report outcome**

Report:

- Commits made, with SHA and title.
- Test commands run and pass/fail status.
- Any deviations from this plan.
- `git status --short --branch`.
