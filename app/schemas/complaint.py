from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from app.models.complaint import PriorityEnum, StatusEnum


class ComplaintCreate(BaseModel):
    citizen_id: int = Field(gt=0)
    directorate_id: int = Field(ge=1, le=2)
    title: str = Field(min_length=5, max_length=150)
    details: str = Field(min_length=10, max_length=20000)
    category: str = Field(min_length=1, max_length=50)
    priority: PriorityEnum = PriorityEnum.MEDIUM
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)


class ComplaintResponse(ComplaintCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tracking_code: str
    status: StatusEnum


class AttachmentCreate(BaseModel):
    file_path: str
    file_type: str
    attachable_type: str
    attachable_id: int


class ProcessingUpdate(BaseModel):
    admin_notes: str = Field(default="", max_length=2000)
    resolution_report: Optional[str] = Field(default=None, max_length=10000)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    priority: Optional[PriorityEnum] = None


class NoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    is_internal: bool = False
