import uuid
from datetime import datetime, date
from typing import TYPE_CHECKING

from sqlalchemy import String, Date, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .application import LoanApplication

class PersonalInfo(Base):
    __tablename__ = "personal_info"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loan_applications.id"), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    
    full_name: Mapped[str] = mapped_column(String)
    id_card_number: Mapped[str] = mapped_column(String, unique=True)
    phone: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    date_of_birth: Mapped[date] = mapped_column(Date)
    address: Mapped[str] = mapped_column(Text)
    
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    application: Mapped["LoanApplication"] = relationship(
        "LoanApplication", 
        back_populates="personal_info"
    )
    
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
