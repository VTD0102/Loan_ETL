from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.dependencies import require_customer
from backend.db.session import get_db
from backend.models.application import ApplicationCreate, ApplicationOut
from backend.models.personal_info import PersonalInfoCreate, PersonalInfoOut
from backend.services import application_service

router = APIRouter()


@router.post("", response_model=ApplicationOut, status_code=201)
def submit_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return application_service.submit(db, current_user["sub"], payload)


@router.get("/me", response_model=ApplicationOut | None)
def get_my_application(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return application_service.get_active(db, current_user["sub"])


@router.get("/{app_id}", response_model=ApplicationOut)
def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return application_service.get_by_id(db, app_id, current_user["sub"])


@router.post("/{app_id}/personal-info", response_model=PersonalInfoOut, status_code=201)
def submit_personal_info(
    app_id: int,
    payload: PersonalInfoCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_customer),
):
    return application_service.submit_personal_info(db, app_id, current_user["sub"], payload)
