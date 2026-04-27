from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import require_customer
from db.session import get_db
from schemas.application import ApplicationCreate, ApplicationRead, ApplicationSummary
from schemas.personal_info import PersonalInfoCreate, PersonalInfoRead
from services import application_service

router = APIRouter()


@router.post("/submit", status_code=201)
def submit_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return application_service.submit(db, current_user["sub"], payload)


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
