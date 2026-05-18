"""
CIC router — Credit Information Center endpoints.

Provides:
  GET  /cic/me              — Customer: xem CIC record của mình
  GET  /cic/lookup/{cccd}   — Admin: tra cứu CIC bất kỳ
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from api.dependencies import get_current_user, require_customer, require_admin
from services import cic_service
from schemas.cic import CICLookupResponse

router = APIRouter(prefix="/cic", tags=["CIC Bureau"])


@router.get("/me", response_model=CICLookupResponse)
def get_my_cic(
    current_user: dict = Depends(require_customer),
    db: Session = Depends(get_db),
):
    """Customer xem CIC record của mình (dựa trên CCCD đã đăng ký)."""
    record = cic_service.get_user_cic(db, current_user["sub"])
    if not record:
        return CICLookupResponse(found=False)
    return CICLookupResponse(found=True, record=record)


@router.get("/lookup/{cccd}", response_model=CICLookupResponse)
def admin_lookup_cic(
    cccd: str,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin tra cứu CIC record theo CCCD bất kỳ."""
    record = cic_service.lookup_by_cccd(db, cccd)
    if not record:
        return CICLookupResponse(found=False)
    return CICLookupResponse(found=True, record=record)
