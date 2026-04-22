from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class PersonalInfoCreate(BaseModel):
    full_name: str
    id_card_number: str
    phone: str
    email: EmailStr
    date_of_birth: date
    address: str


class PersonalInfoOut(PersonalInfoCreate):
    id: int
    application_id: int
    user_id: int
    submitted_at: datetime
