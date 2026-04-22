from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

ApplicationStatus = Literal[
    "AUTO_REJECTED", "PENDING_REVIEW", "ADMIN_REJECTED", "AWAITING_INFO", "INFO_SUBMITTED"
]


class ApplicationCreate(BaseModel):
    monthly_income: float
    loan_amount: float
    term: Literal[12, 36, 60]
    employment_status: str
    dti: float
    is_homeowner: bool
    listing_category: str
    credit_score: float


class ApplicationOut(BaseModel):
    id: int
    user_id: int
    status: ApplicationStatus
    monthly_income: float
    loan_amount: float
    term: int
    employment_status: str
    dti: float
    is_homeowner: bool
    listing_category: str
    credit_score: float
    default_probability: Optional[float]
    risk_level: Optional[str]
    risk_score: Optional[int]
    recommended_amount: Optional[float]
    recommended_term: Optional[int]
    submitted_at: datetime
    reviewed_at: Optional[datetime]
    admin_note: Optional[str]


class AdminReview(BaseModel):
    action: Literal["approve", "reject"]
    admin_note: Optional[str] = None
