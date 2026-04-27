import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, DateTime, Numeric, Integer, Boolean, Text, ForeignKey, func
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
    
    monthly_income: Mapped[Decimal] = mapped_column(Numeric)
    loan_amount: Mapped[Decimal] = mapped_column(Numeric)
    term: Mapped[int] = mapped_column(Integer)
    employment_status: Mapped[str] = mapped_column(String)
    dti: Mapped[Decimal] = mapped_column(Numeric)
    is_homeowner: Mapped[bool] = mapped_column(Boolean)
    listing_category: Mapped[str] = mapped_column(String)
    credit_score: Mapped[int] = mapped_column(Integer)
    
    # Các trường có thể cập nhật sau khi đánh giá, nên cho phép nullable ở cấp database / Python
    default_probability: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recommended_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    recommended_term: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    # Vì bảng này có 2 cột foreign_keys trỏ về user_id và reviewed_by (đều từ users.id),
    # ta nên set rõ foreign_keys trong relationship để SQLAlchemy không bị nhầm.
    user: Mapped["User"] = relationship(
        "User", 
        foreign_keys=[user_id], 
        back_populates="applications"
    )

    personal_info: Mapped[Optional["PersonalInfo"]] = relationship(
        "PersonalInfo", 
        back_populates="application", 
        uselist=False, # Quan hệ 1-1, trả về 1 Object thay vì List
        cascade="all, delete-orphan"
    )
