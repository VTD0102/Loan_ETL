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
from services.model_feature_builder import fetch_previous_applications
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


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
        "income_verifiable_flag":  payload.income_verifiable_flag,
        "age_years":               payload.age_years,
        "gender_male_flag":        payload.gender_male_flag,
        "education_ordinal":       payload.education_ordinal,
        "cnt_children":            payload.cnt_children,
        "cnt_fam_members":         payload.cnt_fam_members,
        "is_married_flag":         payload.is_married_flag,
        # System-computed by ML pipeline
        "credit_score":            prediction.get("credit_score_computed"),
        "dti":                     Decimal(str(prediction.get("hc_dti", 0.0))),
    }


def evaluate(db: Session, user_email: str, payload: ApplicationCreate) -> dict:
    """
    Phase 1 — chạy ML + binary-search suggestion, KHÔNG lưu DB (trừ AUTO_REJECTED).

    Trả về ApplicationEvaluateResponse:
      - AUTO_REJECTED : đã lưu DB, trả lý do + suggestion
      - PENDING_REVIEW: chưa lưu DB, trả is_perfect_fit + suggestion
    """
    user = _get_user(db, user_email)
    _check_active_application(db, user.id)

    # ── CIC enrichment: replace self-reported bureau fields with verified data ──
    cic_comparison = {}
    if user.cccd:
        cic_record = cic_service.lookup_by_cccd(db, user.cccd)
        if cic_record:
            # Blacklist check — reject immediately without ML
            if cic_record.blacklist_flag:
                logger.info("User %s blacklisted in CIC: %s", user.email, cic_record.blacklist_reason)
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
            logger.info("CIC enrichment applied for %s", user.email)

    try:
        prediction = ml_service.predict(payload, db=db, user_id=user.id)
    except ml_service.ModelPredictionError as exc:
        raise HTTPException(503, f"ML model không khả dụng: {exc}") from exc

    prob = prediction["default_probability"]

    if prob > 0.4:
        new_app = LoanApplication(
            user_id=user.id,
            status="AUTO_REJECTED",
            **_build_app_fields(payload, prediction),
            default_probability=prob,
            risk_level="High",
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
            "status":              "AUTO_REJECTED",
            "application_id":      str(new_app.id),
            "default_probability": prob,
            "risk_level":          "High",
            "risk_score":          prediction["risk_score"],
            "credit_score_computed": prediction.get("credit_score_computed", 0),
            "is_perfect_fit":      False,
            "suggested_amount":    prediction["suggested_amount"],
            "suggested_term":      prediction["suggested_term"],
            "model_version":       prediction["model_version"],
        }

    return {
        "status":              "PENDING_REVIEW",
        "application_id":      None,
        "default_probability": prob,
        "risk_level":          prediction["risk_level"],
        "risk_score":          prediction["risk_score"],
        "credit_score_computed": prediction.get("credit_score_computed", 0),
        "is_perfect_fit":      prediction["is_perfect_fit"],
        "suggested_amount":    prediction["suggested_amount"],
        "suggested_term":      prediction["suggested_term"],
        "model_version":       prediction["model_version"],
    }


def confirm(db: Session, user_email: str, payload: ApplicationConfirm) -> dict:
    """
    Phase 2 — user xác nhận (có thể đã điều chỉnh loan/term); lưu vào DB.
    Validate loan_amount ≤ max safe amount trước khi lưu.
    """
    user = _get_user(db, user_email)
    _check_active_application(db, user.id)

    # ── CIC enrichment (same as evaluate) ──
    cic_comparison = {}
    if user.cccd:
        cic_record = cic_service.lookup_by_cccd(db, user.cccd)
        if cic_record:
            if cic_record.blacklist_flag:
                raise HTTPException(400, "Tài khoản bị cấm vay do nằm trong danh sách đen CIC")
            cic_comparison = cic_service.apply_cic_to_payload(payload, cic_record)

    try:
        artifact = ml_service._load()
        previous = fetch_previous_applications(db, user.id)
        validate_confirmed_values(payload, artifact, previous_applications=previous)
        prediction = ml_service.predict(payload, db=db, user_id=user.id)
    except ml_service.ModelPredictionError as exc:
        raise HTTPException(503, f"ML model không khả dụng: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    prob       = prediction["default_probability"]
    app_status = "AUTO_REJECTED" if prob > 0.4 else "PENDING_REVIEW"

    new_app = LoanApplication(
        user_id=user.id,
        status=app_status,
        **_build_app_fields(payload, prediction),
        default_probability=prob,
        risk_level=prediction["risk_level"],
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
        "risk_level":          prediction["risk_level"],
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
