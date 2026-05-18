"""Pydantic schemas for CIC credit bureau records."""
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CICRecordRead(BaseModel):
    """Public CIC data returned by lookup endpoints."""
    id: UUID
    cccd: str
    full_name: Optional[str] = None
    cic_score: Optional[int] = None
    total_active_loans: int = 0
    total_outstanding_debt: Decimal = Decimal("0")
    total_overdue_amount: Decimal = Decimal("0")
    max_dpd_12m: int = 0
    num_credit_inquiries: int = 0
    bad_debt_flag: bool = False
    blacklist_flag: bool = False
    blacklist_reason: Optional[str] = None
    loan_history: Optional[list] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CICLookupResponse(BaseModel):
    """Wrapper for CIC lookup — includes found flag."""
    found: bool
    record: Optional[CICRecordRead] = None


class CICEnrichmentResult(BaseModel):
    """Fields that CIC overwrites on a loan application."""
    num_bureau_records: int
    num_active_credit: int
    total_overdue_amount: Decimal
    max_credit_overdue_days: int
    has_bad_debt: bool
    cic_score: Optional[int] = None
    blacklisted: bool = False
