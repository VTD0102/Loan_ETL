from uuid import UUID
from datetime import datetime
from typing import Optional, Literal, Any
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator
from .personal_info import PersonalInfoRead

ApplicationStatus = Literal[
    "AUTO_REJECTED", "PENDING_REVIEW", "ADMIN_REJECTED",
    "AWAITING_INFO", "INFO_SUBMITTED", "APPROVED", "REJECTED", "PENDING"
]

# v4 loan purpose options (Direction B — rich categories)
LOAN_PURPOSE_OPTIONS = [
    "Education", "Home", "Car", "Business", "Medical", "Personal", "Revolving",
]


class ApplicationBase(BaseModel):
    # ── Core loan features — user input ────────────────────────────────────
    monthly_income: Decimal
    loan_amount: Decimal
    term: int
    employment_status: str
    is_homeowner: bool

    # ── v4: loan_purpose replaces listing_category + dti removed (now computed) ─
    loan_purpose: str

    # ── v3: required features ──────────────────────────────────────────────
    occupation_type: str     # 18 HC categories + 'Unknown'
    years_employed: Decimal  # 0–50
    income_verifiable_flag: bool

    # ── Credit bureau features — required ─────────────────────────────────
    num_bureau_records: int
    num_active_credit: int
    total_overdue_amount: Decimal
    max_credit_overdue_days: int

    # ── Demographics — required ────────────────────────────────────────────
    age_years: int
    gender_male_flag: bool
    education_ordinal: int
    cnt_children: int
    cnt_fam_members: int
    is_married_flag: bool

    @field_validator("term")
    @classmethod
    def validate_term(cls, v):
        if v not in (12, 36, 60):
            raise ValueError("term phải là 12, 36 hoặc 60")
        return v

    @field_validator("loan_purpose")
    @classmethod
    def validate_loan_purpose(cls, v):
        if v not in LOAN_PURPOSE_OPTIONS:
            raise ValueError(f"loan_purpose phải là một trong: {LOAN_PURPOSE_OPTIONS}")
        return v

    @field_validator("education_ordinal")
    @classmethod
    def validate_education(cls, v):
        if not (1 <= v <= 5):
            raise ValueError("education_ordinal phải từ 1 đến 5")
        return v


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationConfirm(ApplicationBase):
    """Dùng khi user xác nhận sau modal gợi ý — có thể điều chỉnh loan_amount và term."""
    pass


class AdminReject(BaseModel):
    admin_note: Optional[str] = None


class ApplicationRead(BaseModel):
    """Response schema — tất cả trường nullable vì DB row cũ có thể thiếu."""
    id: UUID
    user_id: UUID
    status: str

    # Core (luôn có ở row mới)
    monthly_income: Decimal
    loan_amount: Decimal
    term: int
    employment_status: str
    is_homeowner: bool

    # v4: loan_purpose (nullable với row cũ), credit_score/dti now system-computed
    loan_purpose: Optional[str] = None
    credit_score: Optional[int] = None    # system-computed by Stage 1
    dti: Optional[Decimal] = None         # system-computed HC-style DTI

    # v3 (nullable với row cũ)
    occupation_type: Optional[str] = None
    years_employed: Optional[Decimal] = None

    # Bureau (nullable với row cũ)
    num_bureau_records: Optional[int] = None
    num_active_credit: Optional[int] = None
    total_overdue_amount: Optional[Decimal] = None
    max_credit_overdue_days: Optional[int] = None
    income_verifiable_flag: Optional[bool] = None

    # Demographics (nullable với row cũ)
    age_years: Optional[int] = None
    gender_male_flag: Optional[bool] = None
    education_ordinal: Optional[int] = None
    cnt_children: Optional[int] = None
    cnt_fam_members: Optional[int] = None
    is_married_flag: Optional[bool] = None

    # ML results
    default_probability: Optional[Decimal] = None
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    recommended_amount: Optional[Decimal] = None
    recommended_term: Optional[int] = None
    model_version: Optional[str] = None
    feature_snapshot: Optional[dict[str, Any]] = None
    imputed_features: Optional[list[str]] = None

    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None
    admin_note: Optional[str] = None

    personal_info: Optional[PersonalInfoRead] = None

    model_config = ConfigDict(from_attributes=True)


class AdminApplicationRead(ApplicationRead):
    """ApplicationRead + thông tin user cho admin."""
    user_email: Optional[str] = None
    user_username: Optional[str] = None


class ApplicationEvaluateResponse(BaseModel):
    """Kết quả evaluate — chưa lưu vào DB (trừ AUTO_REJECTED)."""
    status: str                           # AUTO_REJECTED | PENDING_REVIEW
    application_id: Optional[str] = None  # chỉ có khi AUTO_REJECTED (đã lưu DB)
    default_probability: float
    risk_level: str                       # Low | Medium | High
    risk_score: int
    credit_score_computed: int            # Stage 1 output — FICO 300–850
    is_perfect_fit: bool                  # True → tự submit thẳng cho admin
    suggested_amount: float
    suggested_term: int
    model_version: Optional[str] = None


class ApplicationSummary(BaseModel):
    id: UUID
    status: str
    loan_amount: Decimal
    term: int
    submitted_at: datetime
    risk_level: Optional[str] = None
    recommended_amount: Optional[Decimal] = None
    recommended_term: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationPendingSummary(BaseModel):
    id: UUID
    user_id: UUID
    loan_amount: Decimal
    term: int
    monthly_income: Decimal
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)
