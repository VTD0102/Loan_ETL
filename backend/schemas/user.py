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

    @field_validator("cccd")
    @classmethod
    def validate_cccd(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 12:
            raise ValueError("CCCD phải gồm đúng 12 chữ số")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRead(UserBase):
    id: UUID
    role: str
    cccd: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead

