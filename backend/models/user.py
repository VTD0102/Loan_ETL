import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Sử dụng TYPE_CHECKING để tránh Circular Import
if TYPE_CHECKING:
    from .application import LoanApplication

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    username: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="customer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    chat_history: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="user")

    # Relationships
    # Dùng string "LoanApplication" thay vì class object trực tiếp
    applications: Mapped[List["LoanApplication"]] = relationship(
        "LoanApplication", 
        back_populates="user",
        foreign_keys="[LoanApplication.user_id]",
        cascade="all, delete-orphan", # Tùy chọn để xóa application khi user bị xóa
    )
