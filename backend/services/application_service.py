from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import not_
from sqlalchemy.exc import IntegrityError

from models.application import LoanApplication
from models.user import User
from models.personal_info import PersonalInfo
from schemas.application import ApplicationCreate, ApplicationConfirm
from schemas.personal_info import PersonalInfoCreate
from services import ml_service, cic_service
from services.loan_suggestion_service import validate_confirmed_values
from services.model_feature_builder import compute_combined_dti, fetch_previous_applications
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

_FALLBACK_TERM = 36  # months — used to estimate installment from outstanding debt

# ── Sanity override: model trained on Home Credit dataset (modest incomes,
# medium-sized loans) tends to over-reject borrowers whose loan is trivially
# small relative to their income. The current_debt_ratio feature is also
# arithmetically unfair on small loans (e.g. $617 overdue / $500 loan = 1.23,
# which the model reads as catastrophic). Apply common-sense business rules
# before persisting an AUTO_REJECTED decision.
_OVERRIDE_LOAN_TO_INCOME_MAX = 0.05      # loan < 5% of monthly income
_OVERRIDE_OVERDUE_TO_INCOME_MAX = 0.10   # overdue < 10% of monthly income
_OVERRIDE_DTI_MAX = 0.30                 # total DTI < 30%
_OVERRIDE_MAX_OVERDUE_DAYS = 30          # not yet "bad debt" by banking convention
_OVERRIDE_PROB_CEILING = 0.15            # capped well below low threshold 0.20


def _apply_sanity_override(
    raw_prob: float,
    payload: ApplicationCreate | ApplicationConfirm,
    *,
    computed_dti: float,
    existing_monthly_debt: float,
) -> tuple[float, str | None]:
    """
    If a loan is obviously safe by banking common-sense, cap the ML probability
    so the borrower is not rejected by an out-of-distribution model prediction.

    Returns (possibly-capped-prob, override_reason or None).
    """
    monthly_income = float(payload.monthly_income or 0)
    loan_amount = float(payload.loan_amount or 0)
    total_overdue = float(getattr(payload, "total_overdue_amount", 0) or 0)
    max_overdue_days = int(getattr(payload, "max_credit_overdue_days", 0) or 0)
    has_bad_debt = bool(getattr(payload, "has_bad_debt", False))

    if monthly_income <= 0 or loan_amount <= 0:
        return raw_prob, None

    loan_to_income = loan_amount / monthly_income
    overdue_to_income = total_overdue / monthly_income

    conditions_met = (
        loan_to_income < _OVERRIDE_LOAN_TO_INCOME_MAX
        and overdue_to_income < _OVERRIDE_OVERDUE_TO_INCOME_MAX
        and computed_dti < _OVERRIDE_DTI_MAX
        and not has_bad_debt
        and max_overdue_days < _OVERRIDE_MAX_OVERDUE_DAYS
    )
    if not conditions_met or raw_prob <= _OVERRIDE_PROB_CEILING:
        return raw_prob, None

    reason = (
        f"Sanity override: khoản vay ({loan_amount:.0f}) chỉ chiếm "
        f"{loan_to_income*100:.2f}% thu nhập tháng, nợ quá hạn "
        f"({total_overdue:.0f}) tương đương {overdue_to_income*100:.2f}% thu nhập, "
        f"DTI tổng {computed_dti*100:.1f}%, không nợ xấu, max overdue {max_overdue_days} ngày. "
        f"Mô hình ML ({raw_prob*100:.1f}%) bị bỏ qua do nằm ngoài phân phối huấn luyện."
    )
    logger.info(
        "Sanity override fired: raw_prob=%.4f → capped=%.4f | loan/income=%.4f overdue/income=%.4f dti=%.4f",
        raw_prob, _OVERRIDE_PROB_CEILING, loan_to_income, overdue_to_income, computed_dti,
    )
    return _OVERRIDE_PROB_CEILING, reason


def _safe_monthly_installment(cic_record) -> float:
    """
    Return the CIC monthly installment, with a safety fallback.

    If total_monthly_installment is 0/null but total_outstanding_debt > 0,
    this is a stale CIC record from before the installment column migration.
    Estimate: outstanding_debt / 36 months as a conservative fallback.
    """
    installment = float(cic_record.total_monthly_installment or 0)
    if installment > 0:
        return installment
    outstanding = float(cic_record.total_outstanding_debt or 0)
    if outstanding > 0:
        return round(outstanding / _FALLBACK_TERM, 2)
    return 0.0

def _get_user(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user


def _check_active_application(db: Session, user_id) -> None:
    active = db.query(LoanApplication).filter(
        LoanApplication.user_id == user_id,
        not_(LoanApplication.status.in_(["AUTO_REJECTED", "ADMIN_REJECTED", "REJECTED"]))
    ).first()
    if active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn đã có đơn đang xử lý",
        )


def _build_app_fields(payload, prediction: dict) -> dict:
    """Build DB fields from user input + system-computed values from ML prediction."""
    return {
        # User input
        "monthly_income":          payload.monthly_income,
        "loan_amount":             payload.loan_amount,
        "term":                    payload.term,
        "employment_status":       payload.employment_status,
        "dti":                     payload.dti,
        "is_homeowner":            payload.is_homeowner,
        "listing_category":        str(payload.listing_category),
        "occupation_type":         payload.occupation_type,
        "years_employed":          payload.years_employed,
        "num_bureau_records":      payload.num_bureau_records,
        "num_active_credit":       payload.num_active_credit,
        "total_overdue_amount":    payload.total_overdue_amount,
        "max_credit_overdue_days": payload.max_credit_overdue_days,
        "has_bad_debt":            payload.has_bad_debt,
        "income_verifiable_flag":  payload.income_verifiable_flag,
        "age_years":               payload.age_years,
        "gender_male_flag":        payload.gender_male_flag,
        "education_ordinal":       payload.education_ordinal,
        "cnt_children":            payload.cnt_children,
        "cnt_fam_members":         payload.cnt_fam_members,
        "is_married_flag":         payload.is_married_flag,
        # System-computed by ML pipeline
        "credit_score":            prediction.get("credit_score_computed"),
    }


def evaluate(db: Session, bureau_db: Session, user_email: str, payload: ApplicationCreate) -> dict:
    """
    Phase 1 — chạy ML + binary-search suggestion, luôn lưu DB.

    Trả về ApplicationEvaluateResponse:
      - AUTO_REJECTED : đã lưu DB, trả lý do + suggestion
      - PENDING_REVIEW: đã lưu DB ngay, trả is_perfect_fit + suggestion + application_id
        (RAG và Chat AI sẽ đọc đúng số liệu đã hiển thị trên UI)
    """
    user = _get_user(db, user_email)
    _check_active_application(db, user.id)

    # ── Compute DTI once and use the same value for display, storage, and ML input ──
    monthly_income = float(payload.monthly_income)
    loan_amount = float(payload.loan_amount)
    term = int(payload.term)

    # Try to get existing debt from CIC
    existing_monthly_debt = 0.0
    cic_record = None
    if user.cccd:
        cic_record = cic_service.lookup_by_cccd(bureau_db, user.cccd)
        if cic_record:
            existing_monthly_debt = _safe_monthly_installment(cic_record)

    computed_dti = compute_combined_dti(
        monthly_income,
        loan_amount,
        term,
        existing_monthly_debt,
    )
    computed_dti_decimal = Decimal(str(round(computed_dti, 4)))
    # CIC monthly debt is passed to model_feature_builder so it can recompute
    # DTI correctly for each binary-search probe in loan_suggestion_service.
    payload.cic_monthly_installment = Decimal(str(existing_monthly_debt))
    payload.dti = None

    # ── CIC enrichment: replace self-reported bureau fields with verified data ──
    cic_comparison = {}
    bureau_features: dict = {}
    if user.cccd and cic_record:
        # Blacklist check — reject immediately without ML
        if cic_record.blacklist_flag:
            logger.info("User %s blacklisted in CIC: %s", user.email, cic_record.blacklist_reason)
            payload.dti = computed_dti_decimal
            new_app = LoanApplication(
                user_id=user.id,
                status="AUTO_REJECTED",
                **_build_app_fields(payload, {"credit_score_computed": cic_record.cic_score, "hc_dti": 0}),
                default_probability=1.0,
                risk_level="High",
                risk_score=0,
                model_version="CIC_BLACKLIST",
                feature_snapshot={"cic_blacklisted": True, "reason": cic_record.blacklist_reason},
            )
            db.add(new_app)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(400, "Bạn đã có đơn đang xử lý")
            db.refresh(new_app)
            return {
                "status": "AUTO_REJECTED",
                "application_id": str(new_app.id),
                "default_probability": 1.0,
                "risk_level": "High",
                "risk_score": 0,
                "credit_score_computed": cic_record.cic_score or 0,
                "is_perfect_fit": False,
                "suggested_amount": 0,
                "suggested_term": 0,
                "model_version": "CIC_BLACKLIST",
                "cic_blacklisted": True,
            }

        # Enrich payload with CIC data (overwrites self-reported values)
        cic_comparison = cic_service.apply_cic_to_payload(payload, cic_record)
        # Store outstanding debt for admin visibility
        cic_comparison["cic_outstanding_debt"] = float(cic_record.total_outstanding_debt or 0)
        cic_comparison["cic_monthly_installment"] = _safe_monthly_installment(cic_record)
        # Derive bureau-only ML features (avg_dpd_recent, num_installs_dpd10, etc.)
        # from CIC mock so they vary across applicants instead of using constant
        # artifact defaults. See cic_service.derive_bureau_features for details.
        bureau_features = cic_service.derive_bureau_features(cic_record)
        if bureau_features:
            cic_comparison["bureau_derived"] = bureau_features
        logger.info("CIC enrichment applied for %s", user.email)

    # ── Build CIC summary for frontend display ──
    cic_summary = None
    if cic_record:
        cic_summary = {
            "found": True,
            "cic_score": cic_record.cic_score,
            "total_active_loans": cic_record.total_active_loans,
            "total_outstanding_debt": float(cic_record.total_outstanding_debt or 0),
            "total_monthly_installment": float(cic_record.total_monthly_installment or 0),
            "total_overdue_amount": float(cic_record.total_overdue_amount or 0),
            "max_dpd_12m": cic_record.max_dpd_12m,
            "num_credit_inquiries": cic_record.num_credit_inquiries,
            "bad_debt_flag": cic_record.bad_debt_flag,
            "blacklist_flag": cic_record.blacklist_flag,
        }
    else:
        cic_summary = {"found": False}

    try:
        prediction = ml_service.predict(
            payload, db=db, user_id=user.id, bureau_features=bureau_features or None,
        )
    except ml_service.ModelPredictionError as exc:
        raise HTTPException(503, f"ML model không khả dụng: {exc}") from exc

    # ── Set the exact DTI used by ML on payload for DB storage ──
    payload.dti = computed_dti_decimal

    raw_prob = prediction["default_probability"]
    prob, override_reason = _apply_sanity_override(
        raw_prob,
        payload,
        computed_dti=computed_dti,
        existing_monthly_debt=existing_monthly_debt,
    )
    app_status = "AUTO_REJECTED" if prob > 0.4 else "PENDING_REVIEW"
    risk_level = "Low" if override_reason else (prediction["risk_level"] if prob <= 0.4 else "High")

    # ── Always save to DB so RAG reads the exact same prediction the UI shows ──
    new_app = LoanApplication(
        user_id=user.id,
        status=app_status,
        **_build_app_fields(payload, prediction),
        default_probability=prob,
        risk_level=risk_level,
        risk_score=prediction["risk_score"],
        recommended_amount=prediction["suggested_amount"],
        recommended_term=prediction["suggested_term"],
        model_version=prediction["model_version"],
        feature_snapshot={**(prediction["feature_snapshot"] or {}), **cic_comparison},
        imputed_features=prediction["imputed_features"],
    )
    db.add(new_app)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Bạn đã có đơn đang xử lý")
    db.refresh(new_app)

    return {
        "status":              app_status,
        "application_id":      str(new_app.id),
        "default_probability": prob,
        "raw_default_probability": raw_prob,
        "override_reason":     override_reason,
        "risk_level":          new_app.risk_level,
        "risk_score":          prediction["risk_score"],
        "credit_score_computed": prediction.get("credit_score_computed", 0),
        "is_perfect_fit":      prediction["is_perfect_fit"],
        "suggested_amount":    prediction["suggested_amount"],
        "suggested_term":      prediction["suggested_term"],
        "model_version":       prediction["model_version"],
        "computed_dti":        computed_dti,
        "cic_summary":         cic_summary,
        "existing_monthly_debt": existing_monthly_debt,
    }


def confirm(db: Session, bureau_db: Session, user_email: str, payload: ApplicationConfirm) -> dict:
    """
    Phase 2 — user xác nhận (có thể đã điều chỉnh loan/term).

    Nếu application_id được gửi kèm và loan_amount/term không thay đổi so với
    bản ghi evaluate đã lưu → reuse ngay, không chạy lại ML.
    (Đây là fix chính cho bug không đồng bộ: RAG đọc đúng số liệu đã hiển thị trên UI.)

    Nếu loan_amount/term khác → xóa bản ghi tạm, chạy lại ML với giá trị mới.
    """
    user = _get_user(db, user_email)

    # ── If evaluate saved an application_id, try to reuse it ──
    existing_app = None
    if payload.application_id:
        existing_app = (
            db.query(LoanApplication)
            .filter(
                LoanApplication.id == payload.application_id,
                LoanApplication.user_id == user.id,
                LoanApplication.status == "PENDING_REVIEW",
            )
            .first()
        )

    # ── Reuse prediction if loan/term unchanged ──
    if existing_app:
        amount_unchanged = abs(float(existing_app.loan_amount) - float(payload.loan_amount)) < 0.01
        term_unchanged   = existing_app.term == int(payload.term)

        if amount_unchanged and term_unchanged:
            # Perfect reuse: UI showed this exact prediction, no ML re-run needed
            logger.info(
                "confirm: reusing evaluate prediction for app %s (loan/term unchanged)",
                existing_app.id,
            )
            return {
                "application_id":      str(existing_app.id),
                "status":              existing_app.status,
                "default_probability": float(existing_app.default_probability or 0),
                "risk_level":          existing_app.risk_level,
                "risk_score":          existing_app.risk_score,
                "suggested_amount":    float(existing_app.recommended_amount or 0),
                "suggested_term":      existing_app.recommended_term,
            }

        # User adjusted loan/term: delete temp record and create fresh one
        logger.info(
            "confirm: loan/term changed (%.0f→%.0f, %s→%s), re-running ML for app %s",
            float(existing_app.loan_amount), float(payload.loan_amount),
            existing_app.term, payload.term,
            existing_app.id,
        )
        db.delete(existing_app)
        db.flush()  # release the unique index before inserting new
    else:
        # Fallback: no matching temp record (e.g. auto-confirm path or direct call)
        _check_active_application(db, user.id)

    # ── CIC enrichment (same as evaluate) ──
    cic_comparison = {}
    existing_monthly_debt = 0.0
    bureau_features: dict = {}
    if user.cccd:
        cic_record = cic_service.lookup_by_cccd(bureau_db, user.cccd)
        if cic_record:
            if cic_record.blacklist_flag:
                raise HTTPException(400, "Tài khoản bị cấm vay do nằm trong danh sách đen CIC")
            cic_comparison = cic_service.apply_cic_to_payload(payload, cic_record)
            # Store outstanding debt for admin visibility
            cic_comparison["cic_outstanding_debt"] = float(cic_record.total_outstanding_debt or 0)
            cic_comparison["cic_monthly_installment"] = _safe_monthly_installment(cic_record)
            existing_monthly_debt = _safe_monthly_installment(cic_record)
            bureau_features = cic_service.derive_bureau_features(cic_record)
            if bureau_features:
                cic_comparison["bureau_derived"] = bureau_features

    payload.cic_monthly_installment = Decimal(str(existing_monthly_debt))
    payload.dti = None

    try:
        artifact = ml_service._load()
        previous = fetch_previous_applications(db, user.id)
        validate_confirmed_values(
            payload, artifact, previous_applications=previous,
            bureau_features=bureau_features or None,
        )
        prediction = ml_service.predict(
            payload, db=db, user_id=user.id, bureau_features=bureau_features or None,
        )
    except ml_service.ModelPredictionError as exc:
        raise HTTPException(503, f"ML model không khả dụng: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    # ── Set the exact DTI used by ML on payload for DB storage ──
    computed_dti = compute_combined_dti(
        payload.monthly_income,
        payload.loan_amount,
        payload.term,
        existing_monthly_debt,
    )
    payload.dti = Decimal(str(round(computed_dti, 4)))

    raw_prob = prediction["default_probability"]
    prob, override_reason = _apply_sanity_override(
        raw_prob,
        payload,
        computed_dti=computed_dti,
        existing_monthly_debt=existing_monthly_debt,
    )
    app_status = "AUTO_REJECTED" if prob > 0.4 else "PENDING_REVIEW"
    risk_level = "Low" if override_reason else prediction["risk_level"]

    new_app = LoanApplication(
        user_id=user.id,
        status=app_status,
        **_build_app_fields(payload, prediction),
        default_probability=prob,
        risk_level=risk_level,
        risk_score=prediction["risk_score"],
        recommended_amount=prediction["suggested_amount"],
        recommended_term=prediction["suggested_term"],
        model_version=prediction["model_version"],
        feature_snapshot={**(prediction["feature_snapshot"] or {}), **cic_comparison},
        imputed_features=prediction["imputed_features"],
    )
    db.add(new_app)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        logger.error(f"IntegrityError in confirm: {e.orig}")
        raise HTTPException(400, "Bạn đã có đơn đang xử lý")
    db.refresh(new_app)

    return {
        "application_id":      str(new_app.id),
        "status":              new_app.status,
        "default_probability": prob,
        "raw_default_probability": raw_prob,
        "override_reason":     override_reason,
        "risk_level":          risk_level,
        "risk_score":          prediction["risk_score"],
        "suggested_amount":    prediction["suggested_amount"],
        "suggested_term":      prediction["suggested_term"],
    }


def list_my_applications(db: Session, user_email: str):
    user = _get_user(db, user_email)
    return (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user.id)
        .order_by(LoanApplication.submitted_at.desc())
        .all()
    )


def get_by_id(db: Session, app_id: str, user_email: str):
    user = _get_user(db, user_email)
    app  = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    if app.user_id != user.id:
        raise HTTPException(403, "Forbidden: Không có quyền truy cập đơn của người khác")
    return app


def submit_personal_info(db: Session, app_id: str, user_email: str, payload: PersonalInfoCreate):
    user = _get_user(db, user_email)
    app  = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    if app.user_id != user.id:
        raise HTTPException(403, "Forbidden: Không có quyền truy cập đơn của người khác")
    if app.status != "AWAITING_INFO":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Trạng thái đơn hiện tại là '{app.status}'. Yêu cầu 'AWAITING_INFO'.",
        )
    if db.query(PersonalInfo).filter(PersonalInfo.application_id == app.id).first():
        raise HTTPException(400, "Thông tin cá nhân cho đơn này đã tồn tại")

    info = PersonalInfo(
        application_id=app.id,
        user_id=user.id,
        full_name=payload.full_name,
        id_card_number=payload.id_card_number,
        phone=payload.phone,
        email=payload.email,
        date_of_birth=payload.date_of_birth,
        address=payload.address,
        bank_account_number=payload.bank_account_number,
        document_urls=payload.document_urls,
    )
    app.status = "INFO_SUBMITTED"
    db.add(info)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Thông tin cá nhân cho đơn này đã tồn tại")
    db.refresh(info)
    return info
