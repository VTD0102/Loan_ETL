from typing import Optional

from sqlalchemy.orm import Session

from models.application import LoanApplication
from models.personal_info import PersonalInfo
from sqlalchemy import func, cast, Date
from datetime import date


def _application_payload(app: LoanApplication) -> dict:
    data = {
        "id": app.id,
        "user_id": app.user_id,
        "status": app.status,
        # Core
        "monthly_income": app.monthly_income,
        "loan_amount": app.loan_amount,
        "term": app.term,
        "employment_status": app.employment_status,
        "dti": app.dti,
        "is_homeowner": app.is_homeowner,
        "listing_category": app.listing_category,
        "credit_score": app.credit_score,
        # v3
        "occupation_type": app.occupation_type,
        "years_employed": app.years_employed,
        # Bureau
        "num_bureau_records": app.num_bureau_records,
        "num_active_credit": app.num_active_credit,
        "total_overdue_amount": app.total_overdue_amount,
        "max_credit_overdue_days": app.max_credit_overdue_days,
        "has_bad_debt": app.has_bad_debt,
        "income_verifiable_flag": app.income_verifiable_flag,
        # Demographics
        "age_years": app.age_years,
        "gender_male_flag": app.gender_male_flag,
        "education_ordinal": app.education_ordinal,
        "cnt_children": app.cnt_children,
        "cnt_fam_members": app.cnt_fam_members,
        "is_married_flag": app.is_married_flag,
        # ML results
        "default_probability": app.default_probability,
        "risk_level": app.risk_level,
        "risk_score": app.risk_score,
        "recommended_amount": app.recommended_amount,
        "recommended_term": app.recommended_term,
        "model_version": app.model_version,
        "feature_snapshot": app.feature_snapshot,
        "imputed_features": app.imputed_features,
        # Timestamps & review
        "submitted_at": app.submitted_at,
        "reviewed_at": app.reviewed_at,
        "reviewed_by": app.reviewed_by,
        "admin_note": app.admin_note,
        # User info (admin only)
        "user_email": None,
        "user_username": None,
    }
    if app.user:
        data["user_email"] = app.user.email
        data["user_username"] = app.user.username
    return data


def list_applications(
    db: Session, 
    status: Optional[str] = None, 
    risk_level: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = 1,
    limit: int = 20
):
    query = db.query(LoanApplication)
    if status is not None:
        query = query.filter(LoanApplication.status == status)
    if risk_level is not None:
        query = query.filter(LoanApplication.risk_level == risk_level)
    if from_date is not None:
        query = query.filter(cast(LoanApplication.submitted_at, Date) >= from_date)
    if to_date is not None:
        query = query.filter(cast(LoanApplication.submitted_at, Date) <= to_date)

    total = query.count()
    skip = (page - 1) * limit
    items = query.order_by(LoanApplication.submitted_at.desc()).offset(skip).limit(limit).all()
    pages = (total + limit - 1) // limit or 1

    return {"items": [_application_payload(app) for app in items], "page": page, "pages": pages, "total": total}


def list_pending(db: Session, page: int = 1, limit: int = 20):
    query = db.query(LoanApplication).filter(LoanApplication.status == 'PENDING_REVIEW')
    total = query.count()
    skip = (page - 1) * limit
    items = query.order_by(LoanApplication.submitted_at.asc()).offset(skip).limit(limit).all()
    pages = (total + limit - 1) // limit or 1

    return {"items": [_application_payload(app) for app in items], "page": page, "pages": pages, "total": total}


def get_by_id(db: Session, app_id: str):
    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    return _application_payload(app)


from fastapi import HTTPException
from models.user import User
from datetime import datetime

def approve_application(db: Session, app_id: str, admin_email: str):
    admin_user = db.query(User).filter(User.email == admin_email).first()
    if not admin_user:
        raise HTTPException(401, "Admin user not found")
        
    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
        
    if app.status != 'PENDING_REVIEW':
        raise HTTPException(400, f"Cannot approve application with status {app.status}")
        
    app.status = 'AWAITING_INFO'
    app.reviewed_at = datetime.now()
    app.reviewed_by = admin_user.id
    
    db.commit()
    db.refresh(app)
    return app

def reject_application(db: Session, app_id: str, admin_email: str, note: Optional[str] = None):
    admin_user = db.query(User).filter(User.email == admin_email).first()
    if not admin_user:
        raise HTTPException(401, "Admin user not found")
        
    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
        
    if app.status != 'PENDING_REVIEW':
        raise HTTPException(400, f"Cannot reject application with status {app.status}")
        
    app.status = 'ADMIN_REJECTED'
    app.reviewed_at = datetime.now()
    app.reviewed_by = admin_user.id
    app.admin_note = note
    
    db.commit()
    db.refresh(app)
    return app


def get_personal_info(db: Session, app_id: str):
    info = db.query(PersonalInfo).filter(PersonalInfo.application_id == app_id).first()
    if not info:
        raise HTTPException(404, "Khách hàng chưa nộp thông tin")
    return info


def dashboard_summary(db: Session):
    today = date.today()
    # base query for today
    today_apps = db.query(LoanApplication).filter(cast(LoanApplication.submitted_at, Date) == today).all()
    
    total = len(today_apps)
    pending = sum(1 for a in today_apps if a.status == "PENDING_REVIEW")
    approved = sum(1 for a in today_apps if a.status == "APPROVED")
    rejected = sum(1 for a in today_apps if a.status == "ADMIN_REJECTED")
    auto_rejected = sum(1 for a in today_apps if a.status == "AUTO_REJECTED")
    
    return {
        "today_total": total,
        "pending_review": pending,
        "approved_today": approved,
        "rejected_today": rejected,
        "auto_rejected_today": auto_rejected
    }

def dashboard_risk_distribution(db: Session):
    distribution = db.query(
        LoanApplication.risk_level, 
        func.count(LoanApplication.id)
    ).group_by(LoanApplication.risk_level).all()
    
    return [
        {"risk_level": r[0] if r[0] else "UNASSIGNED", "count": r[1]} 
        for r in distribution
    ]
