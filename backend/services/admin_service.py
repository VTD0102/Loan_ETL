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
        "education_ordinal": app.education_ordinal,
        "is_married_flag": app.is_married_flag,
        # ML results
        "default_probability": app.default_probability,
        "risk_level": app.risk_level,
        "risk_score": app.risk_score,
        "fico_score": app.fico_score,
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
        "disbursed_at": app.disbursed_at,
        "contract_text": app.contract_text,
        # Personal info
        "personal_info": None,
        # User info (admin only)
        "user_email": None,
        "user_username": None,
    }
    if app.personal_info:
        data["personal_info"] = {
            "id": app.personal_info.id,
            "application_id": app.personal_info.application_id,
            "user_id": app.personal_info.user_id,
            "full_name": app.personal_info.full_name,
            "id_card_number": app.personal_info.id_card_number,
            "phone": app.personal_info.phone,
            "email": app.personal_info.email,
            "date_of_birth": str(app.personal_info.date_of_birth),
            "address": app.personal_info.address,
            "bank_account_number": app.personal_info.bank_account_number,
            "submitted_at": app.personal_info.submitted_at,
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
    
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Lỗi khi duyệt đơn")
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
    
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Lỗi khi từ chối đơn")
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


def _generate_contract(app: LoanApplication, user: "User") -> str:
    """Generate a Vietnamese loan contract in HTML from application + user data."""
    from datetime import timedelta

    loan_amount = float(app.loan_amount)
    term = int(app.term)
    monthly_payment = loan_amount / term if term > 0 else 0
    interest_rate = 8.5  # demo fixed rate
    total_repayment = loan_amount * (1 + interest_rate / 100 * term / 12)
    monthly_with_interest = total_repayment / term if term > 0 else 0

    disbursed = app.disbursed_at or datetime.now()
    end_date = disbursed + timedelta(days=term * 30)
    payment_day = 5  # mỗi tháng ngày 5

    full_name = user.full_name or user.username or "N/A"
    cccd = user.cccd or "N/A"
    phone = user.phone or "N/A"
    address = user.address or "N/A"
    email = user.email

    # Get bank info from personal_info if available
    bank_info = "Chưa cung cấp"
    if app.personal_info:
        bank_info = app.personal_info.bank_account_number or "Chưa cung cấp"

    contract = f"""
<div style="font-family: 'Times New Roman', serif; max-width: 800px; margin: 0 auto; padding: 40px; line-height: 1.8;">
  <div style="text-align: center; margin-bottom: 30px;">
    <h2 style="margin: 0; font-size: 14px; text-transform: uppercase; letter-spacing: 2px;">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</h2>
    <p style="margin: 5px 0; font-size: 13px; font-weight: bold;">Độc lập – Tự do – Hạnh phúc</p>
    <p style="margin: 5px 0; font-size: 13px;">──────── ✦ ────────</p>
  </div>

  <h1 style="text-align: center; font-size: 20px; margin: 20px 0; text-transform: uppercase;">HỢP ĐỒNG VAY VỐN</h1>
  <p style="text-align: center; font-size: 13px; color: #666;">Số: CI-{str(app.id)[:8].upper()}</p>
  <p style="text-align: center; font-size: 13px; color: #666;">Ngày ký: {disbursed.strftime("%d/%m/%Y")}</p>

  <hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;" />

  <h3 style="font-size: 15px;">ĐIỀU 1: CÁC BÊN THAM GIA</h3>
  <p><strong>Bên A (Bên cho vay):</strong> Công ty Tài chính CreditIntel</p>
  <ul style="list-style: none; padding-left: 20px;">
    <li>Địa chỉ: 268 Lý Thường Kiệt, Q.10, TP.HCM</li>
    <li>Đại diện: Ông Nguyễn Văn Admin – Giám đốc Chi nhánh</li>
  </ul>

  <p><strong>Bên B (Bên vay):</strong> {full_name}</p>
  <ul style="list-style: none; padding-left: 20px;">
    <li>CCCD: {cccd}</li>
    <li>Điện thoại: {phone}</li>
    <li>Địa chỉ: {address}</li>
    <li>Email: {email}</li>
    <li>Tài khoản nhận tiền: {bank_info}</li>
  </ul>

  <h3 style="font-size: 15px;">ĐIỀU 2: NỘI DUNG KHOẢN VAY</h3>
  <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
    <tr style="background: #f8f9fa;">
      <td style="padding: 8px 12px; border: 1px solid #dee2e6; font-weight: bold; width: 40%;">Số tiền vay</td>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6;">${loan_amount:,.2f} USD</td>
    </tr>
    <tr>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6; font-weight: bold;">Kỳ hạn</td>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{term} tháng</td>
    </tr>
    <tr style="background: #f8f9fa;">
      <td style="padding: 8px 12px; border: 1px solid #dee2e6; font-weight: bold;">Lãi suất</td>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{interest_rate}% / năm (cố định)</td>
    </tr>
    <tr>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6; font-weight: bold;">Tổng số tiền phải trả</td>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6;">${total_repayment:,.2f} USD</td>
    </tr>
    <tr style="background: #f8f9fa;">
      <td style="padding: 8px 12px; border: 1px solid #dee2e6; font-weight: bold;">Trả góp hàng tháng</td>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6;">${monthly_with_interest:,.2f} USD</td>
    </tr>
    <tr>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6; font-weight: bold;">Ngày trả hàng tháng</td>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6;">Ngày {payment_day} mỗi tháng</td>
    </tr>
    <tr style="background: #f8f9fa;">
      <td style="padding: 8px 12px; border: 1px solid #dee2e6; font-weight: bold;">Ngày giải ngân</td>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{disbursed.strftime("%d/%m/%Y")}</td>
    </tr>
    <tr>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6; font-weight: bold;">Ngày đáo hạn</td>
      <td style="padding: 8px 12px; border: 1px solid #dee2e6;">{end_date.strftime("%d/%m/%Y")}</td>
    </tr>
  </table>

  <h3 style="font-size: 15px;">ĐIỀU 3: QUYỀN VÀ NGHĨA VỤ</h3>
  <p><strong>3.1. Bên B có nghĩa vụ:</strong></p>
  <ul>
    <li>Trả nợ gốc và lãi đúng hạn theo lịch trả nợ.</li>
    <li>Sử dụng vốn vay đúng mục đích đã kê khai.</li>
    <li>Thông báo cho Bên A khi thay đổi thông tin liên hệ.</li>
  </ul>
  <p><strong>3.2. Bên A có quyền:</strong></p>
  <ul>
    <li>Thu hồi nợ trước hạn nếu Bên B vi phạm hợp đồng.</li>
    <li>Áp dụng lãi phạt trả chậm: 150% lãi suất hợp đồng.</li>
  </ul>

  <h3 style="font-size: 15px;">ĐIỀU 4: ĐIỀU KHOẢN CHUNG</h3>
  <p>Hợp đồng có hiệu lực từ ngày ký. Hai bên cam kết thực hiện đúng các điều khoản.</p>
  <p>Mọi tranh chấp sẽ được giải quyết tại Tòa án nhân dân có thẩm quyền.</p>

  <div style="display: flex; justify-content: space-between; margin-top: 50px;">
    <div style="text-align: center; width: 45%;">
      <p style="font-weight: bold;">ĐẠI DIỆN BÊN A</p>
      <p style="color: #999; font-style: italic; margin-top: 60px;">(Ký, ghi rõ họ tên)</p>
      <p style="font-weight: bold;">Nguyễn Văn Admin</p>
    </div>
    <div style="text-align: center; width: 45%;">
      <p style="font-weight: bold;">BÊN B (BÊN VAY)</p>
      <p style="color: #999; font-style: italic; margin-top: 60px;">(Ký, ghi rõ họ tên)</p>
      <p style="font-weight: bold;">{full_name}</p>
    </div>
  </div>

  <p style="text-align: center; margin-top: 40px; font-size: 11px; color: #999;">
    Hợp đồng được lập thành 02 bản, mỗi bên giữ 01 bản có giá trị pháp lý như nhau.<br/>
    Hệ thống CreditIntel — Nền tảng cho vay thông minh.
  </p>
</div>
"""
    return contract.strip()


def disburse_application(db: Session, app_id: str, admin_email: str):
    """Giải ngân khoản vay: cập nhật status → DISBURSED, sinh hợp đồng."""
    admin_user = db.query(User).filter(User.email == admin_email).first()
    if not admin_user:
        raise HTTPException(401, "Admin user not found")

    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")

    if app.status != "INFO_SUBMITTED":
        raise HTTPException(400, f"Chỉ có thể giải ngân đơn có trạng thái INFO_SUBMITTED. Hiện tại: {app.status}")

    borrower = db.query(User).filter(User.id == app.user_id).first()
    if not borrower:
        raise HTTPException(404, "Borrower user not found")

    app.status = "DISBURSED"
    app.disbursed_at = datetime.now()
    app.contract_text = _generate_contract(app, borrower)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Lỗi khi giải ngân")
    db.refresh(app)
    return _application_payload(app)
