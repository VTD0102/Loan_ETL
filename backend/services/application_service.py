from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.models.application import ApplicationCreate, AdminReview
from backend.models.personal_info import PersonalInfoCreate
from backend.services import ml_service


def submit(db: Session, user_id: int, payload: ApplicationCreate):
    # TODO: check user has no active application
    # TODO: call ml_service.predict(payload)
    # TODO: set status = AUTO_REJECTED if default_probability > 0.4, else PENDING_REVIEW
    # TODO: persist loan_applications row
    # TODO: return ApplicationOut
    raise NotImplementedError


def get_active(db: Session, user_id: int):
    # TODO: query latest non-terminal application for user
    raise NotImplementedError


def get_by_id(db: Session, app_id: int, user_id: int):
    # TODO: fetch application, verify ownership
    raise NotImplementedError


def submit_personal_info(db: Session, app_id: int, user_id: int, payload: PersonalInfoCreate):
    # TODO: verify application status == AWAITING_INFO
    # TODO: verify ownership
    # TODO: insert personal_info row
    # TODO: update application status to INFO_SUBMITTED
    raise NotImplementedError
