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

def lookup_by_cccd(db: Session, cccd: str) -> Optional[CICRecord]:
    """Find a CIC record by CCCD. Returns None if not found."""
    return db.query(CICRecord).filter(CICRecord.cccd == cccd).first()


def get_user_cic(db: Session, user_email: str) -> Optional[CICRecord]:
    """Get the CIC record for a logged-in user (via their cccd)."""
    user = db.query(User).filter(User.email == user_email).first()
    if not user or not user.cccd:
        return None
    return lookup_by_cccd(db, user.cccd)


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


def derive_bureau_features(cic: CICRecord) -> dict:
    """
    Derive ML-internal bureau features from CIC mock data so they vary across
    applicants instead of falling through to artifact defaults at inference.

    Returns a dict of feature_name → value. Keys that cannot be derived from
    the current CIC schema (e.g. `cb_queries_30d`, `total_prolongations`) are
    omitted and will fall through to `feature_defaults` in `build_model_input`.

    Approximation note: mock `loan_history` entries are `{lender, amount,
    status, dpd_max}` with no `opened_at`/`closed_at`, so windowed metrics
    (`avg_dpd_recent`, `max_dpd_24m`) collapse to "all loans in history".
    Good enough to break the constant-default behavior; not a substitute
    for retraining on data with matching distribution.
    """
    out: dict = {}

    # num_cb_queries — trivial mapping from existing CIC field.
    if cic.num_credit_inquiries is not None:
        out["num_cb_queries"] = int(cic.num_credit_inquiries)

    history = cic.loan_history or []
    if not history:
        return out

    dpds = [int(loan.get("dpd_max") or 0) for loan in history]

    if dpds:
        out["avg_dpd_recent"] = sum(dpds) / len(dpds)
        out["max_dpd_24m"] = max(dpds)
        out["num_installs_dpd10"] = sum(1 for d in dpds if d > 10)

    overdue_amounts = [
        float(loan.get("amount") or 0)
        for loan in history
        if str(loan.get("status") or "").lower() == "overdue"
    ]
    if overdue_amounts:
        out["max_overdue_amount"] = max(overdue_amounts)

    return out


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
