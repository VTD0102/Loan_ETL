from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies import require_admin
from db.session import get_db
from schemas.application import ApplicationRead, AdminApplicationRead, ApplicationPendingSummary, AdminReject
from schemas.personal_info import PersonalInfoRead
from services import admin_service

router = APIRouter()


@router.get("/applications")
def list_applications(
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.list_applications(
        db, status=status, risk_level=risk_level,
        from_date=from_date, to_date=to_date,
        page=page, limit=limit
    )


@router.get("/applications/pending")
def list_pending(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.list_pending(db, page=page, limit=limit)


@router.get("/applications/{app_id}", response_model=AdminApplicationRead)
def get_application(
    app_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.get_by_id(db, app_id)


@router.post("/applications/{app_id}/approve", response_model=ApplicationRead)
def approve_application(
    app_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    return admin_service.approve_application(db, app_id, current_user["sub"])


@router.post("/applications/{app_id}/reject", response_model=ApplicationRead)
def reject_application(
    app_id: str,
    payload: AdminReject,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    return admin_service.reject_application(db, app_id, current_user["sub"], payload.admin_note)


@router.get("/applications/{app_id}/personal-info", response_model=PersonalInfoRead)
def get_personal_info(
    app_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.get_personal_info(db, app_id)


@router.get("/dashboard/summary")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.dashboard_summary(db)

@router.get("/dashboard/risk-distribution")
def get_dashboard_risk_distribution(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    return admin_service.dashboard_risk_distribution(db)
