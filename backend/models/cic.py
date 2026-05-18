"""
CIC (Credit Information Center) — Simulated third-party credit bureau.

Each record represents a citizen's credit history, looked up by CCCD (12-digit ID).
Independent of the users table — any CCCD can be queried whether or not
the person has an account in CreditIntel.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DateTime, Numeric, Integer, Boolean, Text, func, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CICRecord(Base):
    __tablename__ = "cic_credit_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # ── Lookup key ─────────────────────────────────────────────────────────
    cccd: Mapped[str] = mapped_column(String(12), unique=True, nullable=False, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # ── Credit scoring ─────────────────────────────────────────────────────
    cic_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 300-900

    # ── Active credit summary ──────────────────────────────────────────────
    total_active_loans: Mapped[int] = mapped_column(Integer, default=0)
    total_outstanding_debt: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    total_overdue_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)

    # ── Delinquency ────────────────────────────────────────────────────────
    max_dpd_12m: Mapped[int] = mapped_column(Integer, default=0)  # Max days past due in last 12 months
    num_credit_inquiries: Mapped[int] = mapped_column(Integer, default=0)

    # ── Risk flags ─────────────────────────────────────────────────────────
    bad_debt_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    blacklist_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    blacklist_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Detailed history (JSON array) ──────────────────────────────────────
    # Each entry: {lender, amount, status, opened_at, closed_at, dpd_max}
    loan_history: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # ── Timestamps ─────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
