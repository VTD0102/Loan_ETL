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

class PersonalInfoCreate(PersonalInfoBase):
    pass # application_id is usually inferred from the path parameter during submission

class PersonalInfoRead(PersonalInfoBase):
    id: UUID
    application_id: UUID
    user_id: UUID
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)
