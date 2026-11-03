from pydantic import BaseModel, Field
from typing import Optional, List
from app.models.complaint import PriorityEnum, StatusEnum

class ComplaintCreate(BaseModel):
    citizen_id: int
    directorate_id: int
    title: str = Field(..., min_length=5, max_length=150)
    details: str = Field(..., min_length=10)
    category: str
    priority: Optional[PriorityEnum] = PriorityEnum.MEDIUM
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class ComplaintResponse(ComplaintCreate):
    id: int
    tracking_code: str
    status: StatusEnum

    class Config:
        from_attributes = True

class AttachmentCreate(BaseModel):
    file_path: str
    file_type: str
    attachable_type: str
    attachable_id: int

class AttachmentResponse(BaseModel):
    id: int
    file_path: str
    file_type: str

    class Config:
        from_attributes = True

class ComplaintResponse(ComplaintCreate):
    id: int
    tracking_code: str
    status: StatusEnum
    attachments: List[AttachmentResponse] = []

    class Config:
        from_attributes = True