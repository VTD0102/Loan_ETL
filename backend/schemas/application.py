from uuid import UUID
from datetime import datetime
from typing import Optional, Literal, Any, Union
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from .personal_info import PersonalInfoRead

ApplicationStatus = Literal[
    "AUTO_REJECTED", "PENDING_REVIEW", "ADMIN_REJECTED", "AWAITING_INFO", "INFO_SUBMITTED", "APPROVED", "REJECTED", "PENDING"
]

class ApplicationBase(BaseModel):
    monthly_income: Decimal
    loan_amount: Decimal
    term: int # e.g. 12, 36, 60 months
    employment_status: str
    dti: Decimal
    is_homeowner: bool
    listing_category: Union[str, int]
    credit_score: int
    ext_source_1: Optional[Decimal] = None
    ext_source_3: Optional[Decimal] = None
    num_bureau_records: Optional[int] = None
    num_active_credit: Optional[int] = None
    total_overdue_amount: Optional[Decimal] = None
    max_credit_overdue_days: Optional[int] = None
    has_bad_debt: Optional[bool] = None
    income_verifiable_flag: Optional[bool] = None
    age_years: Optional[int] = None
    gender_male_flag: Optional[bool] = None
    education_ordinal: Optional[int] = None
    cnt_children: Optional[int] = None
    cnt_fam_members: Optional[int] = None
    is_married_flag: Optional[bool] = None

class ApplicationCreate(ApplicationBase):
    pass

class AdminReject(BaseModel):
    admin_note: Optional[str] = None

class ApplicationRead(ApplicationBase):
    id: UUID
    user_id: UUID
    status: str
    
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

    # Quan hệ nested có thể được đọc từ SQLAlchemy ORM bằng from_attributes
    personal_info: Optional[PersonalInfoRead] = None

    model_config = ConfigDict(from_attributes=True)

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
