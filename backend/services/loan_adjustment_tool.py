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


@dataclass(frozen=True)
class LoanAdjustmentProposal:
    loan_amount: Decimal
    term: int
    default_probability: float
    risk_level: str
    risk_score: int
    model_version: str | None = None


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
    passing: list[tuple[tuple[int, float, int, int], LoanAdjustmentProposal]] = []
    best_observed: LoanAdjustmentProposal | None = None

    for amount_index, amount in enumerate(_candidate_amounts(app)):
        for term in SUPPORTED_TERMS:
            payload = application_to_confirm_payload(app, loan_amount=amount, term=term)
            prediction = ml_service.predict(payload, db=db, user_id=user_id)
            proposal = _proposal_from_prediction(payload, prediction)

            if (
                best_observed is None
                or proposal.default_probability < best_observed.default_probability
            ):
                best_observed = proposal

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

            term_distance = abs(int(term) - int(app.term))
            # Product choice: keep the original requested amount when possible;
            # only reduce amount if no original-amount candidate passes.
            rank = (
                amount_index,
                proposal.default_probability,
                term_distance,
                int(term),
            )
            passing.append((rank, proposal))

    if not passing:
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
        message="A lower-risk loan adjustment is available.",
        proposals=proposal_options,
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
    created_at = now or datetime.utcnow()
    expires_at = created_at + timedelta(minutes=PENDING_ACTION_TTL_MINUTES)
    proposal = result.proposal
    if proposal is None:
        raise ValueError("Cannot build pending action without a loan adjustment proposal")
    return {
        "type": "loan_term_adjustment",
        "status": "pending_confirmation",
        "source_application_id": result.source_application_id,
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "proposal": {
            "loan_amount": str(proposal.loan_amount),
            "term": proposal.term,
            "default_probability": proposal.default_probability,
            "risk_level": proposal.risk_level,
            "risk_score": proposal.risk_score,
            "model_version": proposal.model_version,
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
    option_lines = [
        (
            f"Phương án {index}: số tiền {proposal.loan_amount}, "
            f"kỳ hạn {proposal.term} tháng, "
            f"xác suất vỡ nợ {proposal.default_probability:.2%}, "
            f"mức rủi ro {proposal.risk_level}."
        )
        for index, proposal in enumerate(proposals, start=1)
    ]
    return f"{result.message}\n" + "\n".join(option_lines)


def _proposal_to_action_payload(proposal: LoanAdjustmentProposal) -> dict[str, Any]:
    return {
        "loan_amount": str(proposal.loan_amount),
        "term": proposal.term,
        "default_probability": proposal.default_probability,
        "risk_level": proposal.risk_level,
        "risk_score": proposal.risk_score,
        "model_version": proposal.model_version,
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
    amounts = [_to_decimal(app.loan_amount)]
    recommended = getattr(app, "recommended_amount", None)
    if recommended is not None:
        recommended_amount = _to_decimal(recommended)
        if recommended_amount > 0 and recommended_amount != amounts[0]:
            amounts.append(recommended_amount)
    return amounts


def _proposal_from_prediction(
    payload: ApplicationConfirm,
    prediction: dict[str, Any],
) -> LoanAdjustmentProposal:
    return LoanAdjustmentProposal(
        loan_amount=_to_decimal(payload.loan_amount),
        term=int(payload.term),
        default_probability=float(prediction["default_probability"]),
        risk_level=prediction.get("risk_level") or "",
        risk_score=int(prediction.get("risk_score") or 0),
        model_version=prediction.get("model_version"),
    )


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _to_decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))
