import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# Sử dụng TYPE_CHECKING để tránh Circular Import
if TYPE_CHECKING:
    from .application import LoanApplication
    from .chat import ChatSession

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    username: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    cccd: Mapped[Optional[str]] = mapped_column(String(12), unique=True, nullable=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="customer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Relationships
    # Dùng string "LoanApplication" thay vì class object trực tiếp
    applications: Mapped[List["LoanApplication"]] = relationship(
        "LoanApplication", 
        back_populates="user",
        foreign_keys="LoanApplication.user_id",
        cascade="all, delete-orphan", # Tùy chọn để xóa application khi user bị xóa
    )
