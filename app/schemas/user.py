from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional

class CitizenCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    phone: str = Field(..., min_length=8, max_length=20)
    national_id: str = Field(..., min_length=5, max_length=20)
    telegram_id: Optional[int] = None
    identity_card_url: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def name_without_digits(cls, value):
        if any(char.isdigit() for char in value):
            raise ValueError("الاسم يجب ألا يحتوي على أرقام")
        return value

class CitizenResponse(CitizenCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int