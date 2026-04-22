from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.dependencies import require_admin
from backend.db.session import get_db
from backend.models.application import AdminReview, ApplicationOut
from backend.models.personal_info import PersonalInfoOut
from backend.services import admin_service

router = APIRouter()


@router.get("/applications", response_model=list[ApplicationOut])
def list_applications(
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.list_applications(db, status=status, risk_level=risk_level)


@router.get("/applications/pending", response_model=list[ApplicationOut])
def list_pending(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.list_pending(db)


@router.get("/applications/{app_id}", response_model=ApplicationOut)
def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.get_by_id(db, app_id)


@router.post("/applications/{app_id}/review", response_model=ApplicationOut)
def review_application(
    app_id: int,
    payload: AdminReview,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    return admin_service.review(db, app_id, current_user["sub"], payload)


@router.get("/applications/{app_id}/personal-info", response_model=PersonalInfoOut)
def get_personal_info(
    app_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.get_personal_info(db, app_id)


@router.get("/dashboard/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.dashboard_stats(db)
