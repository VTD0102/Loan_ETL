from uuid import UUID
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class PersonalInfoBase(BaseModel):
    full_name: str
    id_card_number: str
    phone: str
    email: EmailStr
    date_of_birth: date
    address: str
    bank_account_number: Optional[str] = None
    document_urls: Optional[list[str]] = None


class PersonalInfoCreate(PersonalInfoBase):
    pass


class PersonalInfoRead(PersonalInfoBase):
    id: UUID
    application_id: UUID
    user_id: UUID
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)
