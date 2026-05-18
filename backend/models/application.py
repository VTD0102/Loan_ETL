import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, Numeric, Integer, Boolean, Text, ForeignKey, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .personal_info import PersonalInfo

class LoanApplication(Base):
    __tablename__ = "loan_applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String, default="pending")

    # ── Core loan fields (8) ───────────────────────────────────────────────
    monthly_income: Mapped[Decimal] = mapped_column(Numeric)
    loan_amount: Mapped[Decimal] = mapped_column(Numeric)
    term: Mapped[int] = mapped_column(Integer)
    employment_status: Mapped[str] = mapped_column(String)
    dti: Mapped[Decimal] = mapped_column(Numeric)
    is_homeowner: Mapped[bool] = mapped_column(Boolean)
    listing_category: Mapped[str] = mapped_column(String)
    credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # v2: stated only, not model input

    # ── v3/v4 new fields ───────────────────────────────────────────────────
    occupation_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    years_employed: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    loan_purpose: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # ── Credit bureau features — nullable for backward compat with old rows ─
    num_bureau_records: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_active_credit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_overdue_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    max_credit_overdue_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_bad_debt: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    income_verifiable_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # ── Demographic features — nullable for backward compat ────────────────
    age_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender_male_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    education_ordinal: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cnt_children: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cnt_fam_members: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_married_flag: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # ── ML prediction results ──────────────────────────────────────────────
    default_probability: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recommended_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    recommended_term: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    feature_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    imputed_features: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="applications")
    personal_info: Mapped[Optional["PersonalInfo"]] = relationship(
        "PersonalInfo", back_populates="application", uselist=False, cascade="all, delete-orphan"
    )
