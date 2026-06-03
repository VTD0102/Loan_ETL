from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from models.application import LoanApplication
from schemas.application import ApplicationConfirm
from services import ml_service
from services.loan_suggestion_service import validate_confirmed_values
from services.model_feature_builder import fetch_previous_applications, infer_existing_monthly_debt

SUPPORTED_TERMS = (12, 24, 36, 48, 60)
AUTO_REVIEW_THRESHOLD = 0.4
PENDING_ACTION_TTL_MINUTES = 30
_MIN_LOAN_AMOUNT = 500


@dataclass(frozen=True)
class LoanAdjustmentProposal:
    loan_amount: Decimal
    term: int
    default_probability: float
    risk_level: str
    risk_score: int
    model_version: str | None = None
    adjustment_strategy: str | None = None
    rationale: str | None = None


@dataclass(frozen=True)
class LoanAdjustmentResult:
    status: str
    source_application_id: str | None
    current_loan_amount: Decimal | None
    current_term: int | None
    current_default_probability: float | None
    proposal: LoanAdjustmentProposal | None
    best_observed: LoanAdjustmentProposal | None
    message: str
    proposals: list[LoanAdjustmentProposal] | None = None


def find_best_reapplication_option(db: Any, user_id: Any) -> LoanAdjustmentResult:
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
            message="No auto-rejected application was found.",
        )

    if getattr(app, "model_version", None) == "CIC_BLACKLIST":
        return LoanAdjustmentResult(
            status="cic_blacklist",
            source_application_id=str(app.id),
            current_loan_amount=app.loan_amount,
            current_term=app.term,
            current_default_probability=_float_or_none(app.default_probability),
            proposal=None,
            best_observed=None,
            message="Application was rejected by CIC blacklist and cannot be adjusted.",
        )

    artifact = ml_service._load()
    previous = fetch_previous_applications(db, user_id)
    best_observed: LoanAdjustmentProposal | None = None
    observed: list[tuple[tuple[float, int, Decimal], LoanAdjustmentProposal]] = []

    for strategy, candidates in _candidate_stages(app):
        passing: list[tuple[tuple[Any, ...], LoanAdjustmentProposal]] = []

        for amount, term in candidates:
            payload = application_to_confirm_payload(app, loan_amount=amount, term=term)
            prediction = ml_service.predict(payload, db=db, user_id=user_id)
            proposal = _proposal_from_prediction(payload, prediction, strategy=strategy)

            if (
                best_observed is None
                or proposal.default_probability < best_observed.default_probability
            ):
                best_observed = proposal
            observed.append((_fallback_rank(proposal), proposal))

            if proposal.default_probability > AUTO_REVIEW_THRESHOLD:
                continue

            try:
                validate_confirmed_values(
                    payload,
                    artifact,
                    previous_applications=previous,
                )
            except ValueError:
                continue

            passing.append((_passing_rank(strategy, app, proposal), proposal))

        if passing:
            passing.sort(key=lambda item: item[0])
            proposal_options = [proposal for _, proposal in passing[:3]]
            return LoanAdjustmentResult(
                status="proposal",
                source_application_id=str(app.id),
                current_loan_amount=app.loan_amount,
                current_term=app.term,
                current_default_probability=_float_or_none(app.default_probability),
                proposal=proposal_options[0],
                best_observed=best_observed,
                message=_proposal_message(strategy),
                proposals=proposal_options,
            )

    if not observed:
        return LoanAdjustmentResult(
            status="no_passing_option",
            source_application_id=str(app.id),
            current_loan_amount=app.loan_amount,
            current_term=app.term,
            current_default_probability=_float_or_none(app.default_probability),
            proposal=None,
            best_observed=best_observed,
            message="No safe adjustment candidate was found.",
        )

    # Fallback: show the best changed form candidates, but never return the
    # unchanged form that was just rejected.
    observed.sort(key=lambda item: item[0])
    fallback_options = [proposal for _, proposal in observed[:3]]
    if fallback_options:
        return LoanAdjustmentResult(
            status="fallback_proposal",
            source_application_id=str(app.id),
            current_loan_amount=app.loan_amount,
            current_term=app.term,
            current_default_probability=_float_or_none(app.default_probability),
            proposal=fallback_options[0],
            best_observed=best_observed,
            message="Không tìm được khoản vay nào dưới ngưỡng tự động duyệt. "
                    "Các phương án dưới đây là form khác tốt nhất hiện có nhưng vẫn cần cải thiện thêm.",
            proposals=fallback_options,
        )

    return LoanAdjustmentResult(
        status="no_passing_option",
        source_application_id=str(app.id),
        current_loan_amount=app.loan_amount,
        current_term=app.term,
        current_default_probability=_float_or_none(app.default_probability),
        proposal=None,
        best_observed=best_observed,
        message="No safe adjustment candidate was found.",
    )


def get_source_application(
    db: Any,
    user_id: Any,
    source_application_id: Any,
) -> LoanApplication | None:
    try:
        app_id = UUID(str(source_application_id))
    except (TypeError, ValueError):
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
    app: Any,
    loan_amount: Decimal | None = None,
    term: int | None = None,
) -> ApplicationConfirm:
    existing_monthly_debt = infer_existing_monthly_debt(
        app.monthly_income,
        app.loan_amount,
        app.term,
        app.dti or Decimal("0"),
    )
    return ApplicationConfirm(
        monthly_income=app.monthly_income,
        loan_amount=loan_amount if loan_amount is not None else app.loan_amount,
        term=term if term is not None else app.term,
        employment_status=app.employment_status,
        dti=None,
        cic_monthly_installment=Decimal(str(round(existing_monthly_debt, 2))),
        is_homeowner=app.is_homeowner,
        listing_category=app.listing_category,
        credit_score=getattr(app, "credit_score", None),
        occupation_type=app.occupation_type or "Unknown",
        years_employed=app.years_employed or Decimal("0"),
        num_bureau_records=app.num_bureau_records or 0,
        num_active_credit=app.num_active_credit or 0,
        total_overdue_amount=app.total_overdue_amount or Decimal("0"),
        max_credit_overdue_days=app.max_credit_overdue_days or 0,
        has_bad_debt=app.has_bad_debt or False,
        income_verifiable_flag=app.income_verifiable_flag or False,
        age_years=app.age_years or 30,
        gender_male_flag=getattr(app, "gender_male_flag", None) or False,
        education_ordinal=app.education_ordinal or 3,
        cnt_children=getattr(app, "cnt_children", None) or 0,
        cnt_fam_members=getattr(app, "cnt_fam_members", None) or 1,
        is_married_flag=app.is_married_flag or False,
    )


def build_pending_action(
    result: LoanAdjustmentResult,
    now: datetime | None = None,
) -> dict[str, Any]:
    created_at = _as_utc(now or datetime.now(timezone.utc))
    expires_at = created_at + timedelta(minutes=PENDING_ACTION_TTL_MINUTES)
    proposal = result.proposal
    if proposal is None:
        raise ValueError("Cannot build pending action without a loan adjustment proposal")
    return {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": result.source_application_id,
        "current_loan_amount": str(result.current_loan_amount) if result.current_loan_amount is not None else None,
        "current_term": result.current_term,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "proposal": {
            "loan_amount": str(proposal.loan_amount),
            "term": proposal.term,
            "default_probability": proposal.default_probability,
            "risk_level": proposal.risk_level,
            "risk_score": proposal.risk_score,
            "model_version": proposal.model_version,
            "adjustment_strategy": proposal.adjustment_strategy,
        },
        "proposals": [
            _proposal_to_action_payload(option)
            for option in (result.proposals or [proposal])
        ],
    }


def is_pending_action_expired(
    action: dict[str, Any],
    now: datetime | None = None,
) -> bool:
    expires_at = action.get("expires_at")
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(expires_at)
    except (TypeError, ValueError):
        return True

    current = now or datetime.utcnow()
    if _is_timezone_aware(expiry) and not _is_timezone_aware(current):
        current = current.replace(tzinfo=timezone.utc)
    elif _is_timezone_aware(current) and not _is_timezone_aware(expiry):
        expiry = expiry.replace(tzinfo=timezone.utc)
    return current >= expiry


def format_result_for_rag(result: LoanAdjustmentResult) -> str:
    if result.proposal is None:
        return result.message

    proposals = result.proposals or [result.proposal]
    option_lines = []
    for index, proposal in enumerate(proposals, start=1):
        line = (
            f"Phương án {index} ({_strategy_text(proposal.adjustment_strategy)}): "
            f"số tiền {proposal.loan_amount}, "
            f"kỳ hạn {proposal.term} tháng, "
            f"xác suất vỡ nợ {proposal.default_probability:.2%}, "
            f"mức rủi ro {proposal.risk_level}."
        )
        if proposal.rationale:
            line += f" Lý do đề xuất: {proposal.rationale}"
        option_lines.append(line)
    return f"{result.message}\n" + "\n".join(option_lines)


def _proposal_to_action_payload(proposal: LoanAdjustmentProposal) -> dict[str, Any]:
    return {
        "loan_amount": str(proposal.loan_amount),
        "term": proposal.term,
        "default_probability": proposal.default_probability,
        "risk_level": proposal.risk_level,
        "risk_score": proposal.risk_score,
        "model_version": proposal.model_version,
        "adjustment_strategy": proposal.adjustment_strategy,
    }


def _latest_auto_rejected_application(db: Any, user_id: Any) -> LoanApplication | None:
    return (
        db.query(LoanApplication)
        .filter(
            LoanApplication.user_id == user_id,
            LoanApplication.status == "AUTO_REJECTED",
        )
        .order_by(LoanApplication.submitted_at.desc())
        .first()
    )


def _candidate_amounts(app: Any) -> list[Decimal]:
    original = _to_decimal(app.loan_amount)
    amounts = [original]
    recommended = getattr(app, "recommended_amount", None)
    if recommended is not None:
        recommended_amount = _to_decimal(recommended)
        if recommended_amount > 0 and recommended_amount != original:
            amounts.append(recommended_amount)
    # Add reduced amounts: 75%, 50%, 25% of original
    for fraction in (Decimal("0.75"), Decimal("0.50"), Decimal("0.25")):
        reduced = (original * fraction).quantize(Decimal("1"))
        if reduced >= _MIN_LOAN_AMOUNT and reduced not in amounts:
            amounts.append(reduced)
    # Always include minimum loan amount as last resort
    min_amount = _to_decimal(_MIN_LOAN_AMOUNT)
    if min_amount not in amounts:
        amounts.append(min_amount)
    return amounts


def _candidate_stages(app: Any) -> list[tuple[str, list[tuple[Decimal, int]]]]:
    original_amount = _to_decimal(app.loan_amount)
    current_term = int(app.term)
    max_term = max(SUPPORTED_TERMS)
    stages: list[tuple[str, list[tuple[Decimal, int]]]] = []

    higher_terms = [term for term in SUPPORTED_TERMS if term > current_term]
    if higher_terms:
        stages.append(("extend_term", [(original_amount, term) for term in higher_terms]))

    reduced_amounts = [
        amount for amount in _candidate_amounts(app)
        if amount < original_amount
    ]
    if reduced_amounts:
        stages.append(("reduce_amount", [(amount, max_term) for amount in reduced_amounts]))

    return stages


def _passing_rank(
    strategy: str,
    app: Any,
    proposal: LoanAdjustmentProposal,
) -> tuple[Any, ...]:
    original_amount = _to_decimal(app.loan_amount)
    current_term = int(app.term)
    if strategy == "reduce_amount":
        reduction = original_amount - proposal.loan_amount
        return (reduction, proposal.default_probability, -proposal.loan_amount)
    return (
        proposal.term - current_term,
        proposal.default_probability,
        proposal.term,
    )


def _change_magnitude(app: Any, proposal: LoanAdjustmentProposal) -> float:
    """Tổng tỉ lệ thay đổi so với đơn gốc (giảm tiền + tăng kỳ hạn). Nhỏ = gần gốc."""
    original_amount = _to_decimal(app.loan_amount)
    current_term = int(app.term)
    amount_change = 0.0
    if original_amount > 0:
        reduction = max(original_amount - proposal.loan_amount, Decimal("0"))
        amount_change = float(reduction) / float(original_amount)
    term_change = 0.0
    if current_term > 0:
        term_change = max(proposal.term - current_term, 0) / current_term
    return round(amount_change + term_change, 6)


def _unified_rank(app: Any, proposal: LoanAdjustmentProposal) -> tuple[Any, ...]:
    """Khoá sort liên-strategy: ưu tiên thay đổi ít nhất, rồi prob thấp, rồi số tiền
    lớn hơn, rồi kỳ hạn ngắn hơn."""
    return (
        _change_magnitude(app, proposal),
        proposal.default_probability,
        -proposal.loan_amount,
        proposal.term,
    )


def _fallback_rank(proposal: LoanAdjustmentProposal) -> tuple[float, int, Decimal]:
    return (
        proposal.default_probability,
        -proposal.term,
        -proposal.loan_amount,
    )


def _proposal_message(strategy: str) -> str:
    if strategy == "reduce_amount":
        return (
            "Đã thử đến kỳ hạn tối đa 60 tháng. "
            "Có thể nộp form khác bằng cách giảm số tiền vay."
        )
    return (
        "Có thể nộp form khác bằng cách giữ nguyên số tiền vay "
        "và tăng kỳ hạn trả nợ."
    )


def _strategy_text(strategy: str | None) -> str:
    if strategy == "reduce_amount":
        return "giảm số tiền vay"
    if strategy == "extend_term":
        return "tăng kỳ hạn"
    if strategy == "both":
        return "điều chỉnh số tiền và kỳ hạn"
    return "điều chỉnh khoản vay"


def _proposal_from_prediction(
    payload: ApplicationConfirm,
    prediction: dict[str, Any],
    strategy: str | None = None,
    rationale: str | None = None,
) -> LoanAdjustmentProposal:
    return LoanAdjustmentProposal(
        loan_amount=_to_decimal(payload.loan_amount),
        term=int(payload.term),
        default_probability=float(prediction["default_probability"]),
        risk_level=prediction.get("risk_level") or "",
        risk_score=int(prediction.get("risk_score") or 0),
        model_version=prediction.get("model_version"),
        adjustment_strategy=strategy,
        rationale=rationale,
    )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _as_utc(value: datetime) -> datetime:
    if _is_timezone_aware(value):
        return value.astimezone(timezone.utc)
    return value.replace(tzinfo=timezone.utc)


def _to_decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))
