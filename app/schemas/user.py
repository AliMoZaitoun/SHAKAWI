from pydantic import BaseModel, Field
from typing import Optional

class CitizenCreate(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    phone: str = Field(..., min_length=8, max_length=20)
    national_id: str = Field(..., min_length=5, max_length=20)
    telegram_id: Optional[int] = None
    identity_card_url: Optional[str] = None

class CitizenResponse(CitizenCreate):
    id: int

    class Config:
        from_attributes = True