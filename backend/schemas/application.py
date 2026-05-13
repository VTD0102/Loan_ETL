from uuid import UUID
from datetime import datetime
from typing import Optional, Literal
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
    listing_category: str | int
    credit_score: int

class ApplicationCreate(ApplicationBase):
    pass

class AdminReject(BaseModel):
    admin_note: Optional[str] = None

class ApplicationRead(ApplicationBase):
    id: UUID
    user_id: UUID
    user_email: Optional[str] = None
    user_username: Optional[str] = None
    status: str
    
    default_probability: Optional[Decimal] = None
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    recommended_amount: Optional[Decimal] = None
    recommended_term: Optional[int] = None
    
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
    user_email: Optional[str] = None
    user_username: Optional[str] = None
    loan_amount: Decimal
    term: int
    monthly_income: Decimal
    risk_level: Optional[str] = None
    risk_score: Optional[int] = None
    submitted_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
