from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str
    cccd: str
    full_name: str
    phone: str
    address: str

    @field_validator("cccd")
    @classmethod
    def validate_cccd(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 12:
            raise ValueError("CCCD phải gồm đúng 12 chữ số")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not v.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise ValueError("Số điện thoại không hợp lệ")
        if len(v) < 9 or len(v) > 15:
            raise ValueError("Số điện thoại phải từ 9 đến 15 ký tự")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRead(UserBase):
    id: UUID
    role: str
    cccd: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
