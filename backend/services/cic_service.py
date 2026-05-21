"""
cic_service.py — CIC (Credit Information Center) business logic.

Simulates a third-party credit bureau. Provides:
  - lookup_by_cccd: find a CIC record by CCCD
  - enrich_from_cic: map CIC data → loan application bureau fields
  - get_user_cic: convenience to get CIC for a logged-in user
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.cic import CICRecord
from models.user import User
from schemas.cic import CICEnrichmentResult

logger = logging.getLogger(__name__)


# ── Lookup ────────────────────────────────────────────────────────────────────

def lookup_by_cccd(bureau_db: Session, cccd: str) -> Optional[CICRecord]:
    """Find a CIC record by CCCD. Returns None if not found."""
    return bureau_db.query(CICRecord).filter(CICRecord.cccd == cccd).first()


def get_user_cic(db: Session, bureau_db: Session, user_email: str) -> Optional[CICRecord]:
    """Get the CIC record for a logged-in user (via their cccd)."""
    user = db.query(User).filter(User.email == user_email).first()
    if not user or not user.cccd:
        return None
    return lookup_by_cccd(bureau_db, user.cccd)


def create_bureau_profile_if_missing(bureau_db: Session, cccd: str, full_name: str) -> CICRecord:
    """
    Ensure a CIC profile exists for the given CCCD.
    If it does not exist, simulate an external bureau generation
    and persist the profile.
    """
    existing = lookup_by_cccd(bureau_db, cccd)
    if existing:
        return existing

    from services.synthetic_service import generate_bureau_profile_data
    cic_data = generate_bureau_profile_data(cccd, full_name)
    
    new_cic = CICRecord(
        cccd=cic_data["cccd"],
        full_name=cic_data["full_name"],
        cic_score=cic_data.get("cic_score"),
        total_active_loans=cic_data.get("total_active_loans", 0),
        total_outstanding_debt=cic_data.get("total_outstanding_debt", 0),
        total_monthly_installment=cic_data.get("total_monthly_installment", 0),
        total_overdue_amount=cic_data.get("total_overdue_amount", 0),
        max_dpd_12m=cic_data.get("max_dpd_12m", 0),
        num_credit_inquiries=cic_data.get("num_credit_inquiries", 0),
        bad_debt_flag=cic_data.get("bad_debt_flag", False),
        blacklist_flag=cic_data.get("blacklist_flag", False),
        blacklist_reason=cic_data.get("blacklist_reason"),
        loan_history=cic_data.get("loan_history", []),
    )
    bureau_db.add(new_cic)
    bureau_db.commit()
    bureau_db.refresh(new_cic)
    logger.info("Generated new bureau profile for CCCD: %s", cccd)
    return new_cic


# ── Enrichment ────────────────────────────────────────────────────────────────

def enrich_from_cic(cic: CICRecord) -> CICEnrichmentResult:
    """
    Map CIC record fields → the bureau fields used by the ML model.

    These fields REPLACE the user's self-reported values, giving the model
    verified data from the credit bureau instead of potentially inaccurate
    self-declarations.
    """
    num_loans_in_history = len(cic.loan_history) if cic.loan_history else 0

    return CICEnrichmentResult(
        num_bureau_records=num_loans_in_history,
        num_active_credit=cic.total_active_loans,
        total_overdue_amount=cic.total_overdue_amount or Decimal("0"),
        max_credit_overdue_days=cic.max_dpd_12m,
        has_bad_debt=cic.bad_debt_flag,
        cic_score=cic.cic_score,
        blacklisted=cic.blacklist_flag,
    )


def apply_cic_to_payload(payload, cic: CICRecord) -> dict:
    """
    Apply CIC data to an application payload object.

    Returns a dict with the original self-reported values (for audit)
    and mutates the payload in-place with CIC-verified values.
    """
    enrichment = enrich_from_cic(cic)

    # Save original self-reported values for admin comparison
    self_reported = {
        "self_num_bureau_records": int(payload.num_bureau_records),
        "self_num_active_credit": int(payload.num_active_credit),
        "self_total_overdue_amount": float(payload.total_overdue_amount),
        "self_max_credit_overdue_days": int(payload.max_credit_overdue_days),
        "self_has_bad_debt": bool(payload.has_bad_debt),
    }

    # Overwrite with CIC-verified data
    payload.num_bureau_records = enrichment.num_bureau_records
    payload.num_active_credit = enrichment.num_active_credit
    payload.total_overdue_amount = enrichment.total_overdue_amount
    payload.max_credit_overdue_days = enrichment.max_credit_overdue_days
    payload.has_bad_debt = enrichment.has_bad_debt

    return {
        "cic_applied": True,
        "cic_score": enrichment.cic_score,
        "cic_blacklisted": enrichment.blacklisted,
        **self_reported,
    }
