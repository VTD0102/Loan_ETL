from typing import Optional

from sqlalchemy.orm import Session

from backend.models.application import AdminReview


def list_applications(db: Session, status: Optional[str], risk_level: Optional[str]):
    # TODO: query loan_applications with optional filters
    raise NotImplementedError


def list_pending(db: Session):
    # TODO: query loan_applications WHERE status = 'PENDING_REVIEW'
    raise NotImplementedError


def get_by_id(db: Session, app_id: int):
    # TODO: fetch application or raise 404
    raise NotImplementedError


def review(db: Session, app_id: int, admin_id: int, payload: AdminReview):
    # TODO: verify status == PENDING_REVIEW
    # TODO: approve → AWAITING_INFO, reject → ADMIN_REJECTED
    # TODO: set reviewed_at, reviewed_by, admin_note
    raise NotImplementedError


def get_personal_info(db: Session, app_id: int):
    # TODO: fetch personal_info for application or raise 404
    raise NotImplementedError


def dashboard_stats(db: Session):
    # TODO: aggregate counts by status, risk_level, date
    raise NotImplementedError
