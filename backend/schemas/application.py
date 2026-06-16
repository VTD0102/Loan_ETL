from uuid import UUID
from datetime import datetime
from typing import Optional, Literal, Any, Union
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, field_validator
from .personal_info import PersonalInfoRead

ApplicationStatus = Literal[
    "AUTO_REJECTED", "PENDING_REVIEW", "ADMIN_REJECTED",
    "AWAITING_INFO", "INFO_SUBMITTED", "APPROVED", "REJECTED", "PENDING",
    "DISBURSED"
]


class ApplicationBase(BaseModel):
    # ── Core loan features (8) — always required ───────────────────────────
    monthly_income: Decimal
    loan_amount: Decimal
    term: int
    employment_status: str
    dti: Optional[Decimal] = None              # Auto-computed, stored after ML predict
    cic_monthly_installment: Decimal = Decimal("0")  # Backend-set from CIC; never user-supplied
    is_homeowner: bool
    listing_category: Union[str, int]

    # ── v3: new required features ──────────────────────────────────────────
    occupation_type: str     # 18 HC categories + 'Unknown'
    years_employed: Decimal  # 0–50

    # ── Credit bureau features — auto-filled from CIC, optional for user ──
    num_bureau_records: Optional[int] = 0
    num_active_credit: Optional[int] = 0
    total_overdue_amount: Optional[Decimal] = Decimal("0")
    max_credit_overdue_days: Optional[int] = 0
    has_bad_debt: Optional[bool] = False
    income_verifiable_flag: Optional[bool] = True

    # ── Demographics used by v4 ────────────────────────────────────────────
    age_years: int
    education_ordinal: int
    is_married_flag: bool

    @field_validator("term")
    @classmethod
    def validate_term(cls, v):
        if v not in (12, 24, 36, 48, 60):
            raise ValueError("term phải là 12, 24, 36, 48 hoặc 60")
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
    application_id: Optional[str] = None  # ID đơn tạm từ evaluate — để reuse prediction


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
    dti: Optional[Decimal] = None
    is_homeowner: bool
    listing_category: Optional[Union[str, int]] = None

    # v3 (nullable với row cũ)
    occupation_type: Optional[str] = None
    years_employed: Optional[Decimal] = None

    # Bureau (nullable với row cũ)
    num_bureau_records: Optional[int] = None
    num_active_credit: Optional[int] = None
    total_overdue_amount: Optional[Decimal] = None
    max_credit_overdue_days: Optional[int] = None
    has_bad_debt: Optional[bool] = None
    income_verifiable_flag: Optional[bool] = None

    # Demographics (nullable với row cũ)
    age_years: Optional[int] = None
    education_ordinal: Optional[int] = None
    is_married_flag: Optional[bool] = None

    # ML results
    default_probability: Optional[Decimal] = None
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    fico_score: Optional[int] = None
    recommended_amount: Optional[Decimal] = None
    recommended_term: Optional[int] = None
    model_version: Optional[str] = None
    feature_snapshot: Optional[dict[str, Any]] = None
    imputed_features: Optional[list[str]] = None

    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None
    admin_note: Optional[str] = None
    disbursed_at: Optional[datetime] = None
    contract_text: Optional[str] = None

    personal_info: Optional[PersonalInfoRead] = None

    model_config = ConfigDict(from_attributes=True)


class AdminApplicationRead(ApplicationRead):
    """ApplicationRead + thông tin user cho admin."""
    user_email: Optional[str] = None
    user_username: Optional[str] = None


class ApplicationEvaluateResponse(BaseModel):
    """Kết quả evaluate — luôn lưu vào DB với status PENDING_REVIEW hoặc AUTO_REJECTED."""
    status: str                           # AUTO_REJECTED | PENDING_REVIEW
    application_id: str                   # Luôn có — đã lưu DB để RAG đọc đúng số liệu
    default_probability: float
    raw_default_probability: Optional[float] = None  # ML output before sanity override
    override_reason: Optional[str] = None # Set when sanity override capped raw_prob
    risk_level: str                       # Low | Medium | High
    risk_score: int
    is_perfect_fit: bool                  # True → tự submit thẳng cho admin
    suggested_amount: float
    suggested_term: int
    model_version: Optional[str] = None
    computed_dti: Optional[float] = None  # Auto-computed DTI ratio
    cic_summary: Optional[dict] = None    # CIC info summary for display
    existing_monthly_debt: Optional[float] = None  # For frontend reactive DTI recalc
    fico_score: Optional[int] = None      # Scorecard LR 300–850, computed at submission


class ApplicationSummary(BaseModel):
    id: UUID
    status: str
    loan_amount: Decimal
    term: int
    submitted_at: datetime
    risk_level: Optional[str] = None
    recommended_amount: Optional[Decimal] = None
    recommended_term: Optional[int] = None
    disbursed_at: Optional[datetime] = None
    contract_text: Optional[str] = None

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
