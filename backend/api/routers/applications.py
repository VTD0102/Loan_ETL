from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List

from api.dependencies import require_customer
from db.session import get_db
from schemas.application import (
    ApplicationCreate,
    ApplicationConfirm,
    ApplicationRead,
    ApplicationSummary,
    ApplicationEvaluateResponse,
)
from schemas.personal_info import PersonalInfoCreate, PersonalInfoRead
from services import application_service

router = APIRouter()


@router.post("/evaluate", response_model=ApplicationEvaluateResponse, status_code=200)
def evaluate_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    """
    Phase 1 — Đánh giá đơn vay (ML + binary-search suggestion). Không lưu DB trừ AUTO_REJECTED.
    """
    return application_service.evaluate(db, current_user["sub"], payload)


@router.post("/confirm", status_code=201)
def confirm_application(
    payload: ApplicationConfirm,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    """
    Phase 2 — Lưu đơn sau khi user xác nhận. Validate loan ≤ max safe, trả 422 nếu vượt.
    """
    return application_service.confirm(db, current_user["sub"], payload)


@router.get("/me", response_model=list[ApplicationSummary])
def list_my_applications(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return application_service.list_my_applications(db, current_user["sub"])


@router.get("/{app_id}", response_model=ApplicationRead)
def get_application(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return application_service.get_by_id(db, app_id, current_user["sub"])


@router.post("/{app_id}/personal-info", response_model=PersonalInfoRead, status_code=201)
def submit_personal_info(
    app_id: str,
    payload: PersonalInfoCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return application_service.submit_personal_info(db, app_id, current_user["sub"], payload)


@router.post("/{app_id}/documents", status_code=201)
async def upload_documents(
    app_id: str,
    bank_account_number: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    """Upload minh chứng tài sản/công việc + số tài khoản ngân hàng."""
    from services.document_service import upload_documents as _upload
    return await _upload(db, app_id, current_user["sub"], bank_account_number, files)
