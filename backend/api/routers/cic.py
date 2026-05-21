"""
CIC router — Credit Information Center + Synthetic Data endpoints.

Provides:
  GET  /cic/me                          — Customer: xem CIC record của mình
  GET  /cic/lookup/{cccd}               — Admin: tra cứu CIC bất kỳ
  POST /cic/synthetic/generate?count=N  — Admin: sinh N khoản vay giả lập
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db.session import get_db, get_bureau_db
from api.dependencies import get_current_user, require_customer, require_admin
from services import cic_service, synthetic_service
from schemas.cic import CICLookupResponse

router = APIRouter(prefix="/cic", tags=["CIC Bureau"])


@router.get("/me", response_model=CICLookupResponse)
def get_my_cic(
    current_user: dict = Depends(require_customer),
    db: Session = Depends(get_db),
    bureau_db: Session = Depends(get_bureau_db),
):
    """Customer xem CIC record của mình (dựa trên CCCD đã đăng ký)."""
    record = cic_service.get_user_cic(db, bureau_db, current_user["sub"])
    if not record:
        return CICLookupResponse(found=False)
    return CICLookupResponse(found=True, record=record)


@router.get("/lookup/{cccd}", response_model=CICLookupResponse)
def admin_lookup_cic(
    cccd: str,
    current_user: dict = Depends(require_admin),
    bureau_db: Session = Depends(get_bureau_db),
):
    """Admin tra cứu CIC record theo CCCD bất kỳ."""
    record = cic_service.lookup_by_cccd(bureau_db, cccd)
    if not record:
        return CICLookupResponse(found=False)
    return CICLookupResponse(found=True, record=record)


@router.post("/synthetic/generate")
def generate_synthetic(
    count: int = Query(default=10, ge=1, le=100, description="Số khoản vay cần sinh"),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db),
    bureau_db: Session = Depends(get_bureau_db),
):
    """
    Admin trigger: sinh N khoản vay giả lập.

    Mỗi khoản vay = 1 User mới + 1 CIC record + 1 LoanApplication
    chạy qua ML pipeline thật. Phân bố: 60% good / 25% risky / 15% defaulter.
    """
    stats = synthetic_service.generate_batch(db, bureau_db, count=count)
    return stats

