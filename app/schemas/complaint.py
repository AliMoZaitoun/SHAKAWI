from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional
from typing import Literal
from app.models.complaint import PriorityEnum, StatusEnum


class ComplaintCreate(BaseModel):
    citizen_id: int = Field(gt=0)
    directorate_id: int = Field(ge=1)
    title: str = Field(min_length=5, max_length=150)
    details: str = Field(min_length=10, max_length=20000)
    category: Optional[str] = Field(default=None, min_length=1, max_length=50)
    complaint_type_id: Optional[int] = Field(default=None, gt=0)
    priority: PriorityEnum = PriorityEnum.MEDIUM
    is_public: bool = False
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_category_source(self):
        if self.complaint_type_id is None and not self.category:
            raise ValueError("اختر نوع الشكوى")
        return self


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
    reason: str = Field(default="", max_length=1000)


class NoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    is_internal: bool = False
    audience: Optional[Literal["internal", "private", "public"]] = None
