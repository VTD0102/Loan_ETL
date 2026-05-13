from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import not_

from models.application import LoanApplication
from models.user import User
from models.personal_info import PersonalInfo
from schemas.application import ApplicationCreate
from schemas.personal_info import PersonalInfoCreate
from services import ml_service

def submit(db: Session, user_email: str, payload: ApplicationCreate):
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(401, "User not found")

    # Kiểm tra xem user có đơn nào đang xử lý chưa
    active_app = db.query(LoanApplication).filter(
        LoanApplication.user_id == user.id,
        not_(LoanApplication.status.in_(['AUTO_REJECTED', 'ADMIN_REJECTED']))
    ).first()

    if active_app:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn đã có đơn đang xử lý"
        )

    # Gọi service ML (Mô hình sẽ fallback logic Mock nếu pkl chưa đồng bộ Schema)
    prediction = ml_service.predict(payload)
    prob = prediction.get("default_probability", 0.0)
    
    # Auto-reject nếu tỉ lệ bùng nợ > 0.4
    app_status = "AUTO_REJECTED" if prob > 0.4 else "PENDING_REVIEW"

    new_app = LoanApplication(
        user_id=user.id,
        status=app_status,
        monthly_income=payload.monthly_income,
        loan_amount=payload.loan_amount,
        term=payload.term,
        employment_status=payload.employment_status,
        dti=payload.dti,
        is_homeowner=payload.is_homeowner,
        listing_category=payload.listing_category,
        credit_score=payload.credit_score,
        default_probability=prob,
        risk_level=prediction.get("risk_level"),
        risk_score=prediction.get("risk_score"),
        recommended_amount=prediction.get("recommended_amount"),
        recommended_term=prediction.get("recommended_term")
    )

    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return {
        "application_id": str(new_app.id),
        "status": new_app.status,
        "prediction": prediction,
        **prediction,
    }

def list_my_applications(db: Session, user_email: str):
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(401, "User not found")
        
    apps = db.query(LoanApplication).filter(LoanApplication.user_id == user.id)\
        .order_by(LoanApplication.submitted_at.desc())\
        .all()
    return apps

def get_by_id(db: Session, app_id: str, user_email: str):
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(401, "User not found")
        
    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
        
    if app.user_id != user.id:
        raise HTTPException(403, "Forbidden: Không có quyền truy cập đơn của người khác")
        
    return app

def submit_personal_info(db: Session, app_id: str, user_email: str, payload: PersonalInfoCreate):
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(401, "User not found")

    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")

    if app.user_id != user.id:
        raise HTTPException(403, "Forbidden: Không có quyền truy cập đơn của người khác")

    if app.status != 'AWAITING_INFO':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Trạng thái đơn hiện tại là '{app.status}'. API yêu cầu 'AWAITING_INFO'."
        )

    existing_info = db.query(PersonalInfo).filter(PersonalInfo.application_id == app.id).first()
    if existing_info:
        raise HTTPException(400, "Thông tin cá nhân cho đơn này đã tồn tại")

    info = PersonalInfo(
        application_id=app.id,
        user_id=user.id,
        full_name=payload.full_name,
        id_card_number=payload.id_card_number,
        phone=payload.phone,
        email=payload.email,
        date_of_birth=payload.date_of_birth,
        address=payload.address
    )
    
    app.status = 'INFO_SUBMITTED'
    
    db.add(info)
    db.commit()
    db.refresh(info)
    
    return info
