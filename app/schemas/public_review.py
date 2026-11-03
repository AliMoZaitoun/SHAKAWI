from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReportInput(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("يرجى توضيح السبب بخمسة أحرف على الأقل")
        return value


class ReviewInput(ReportInput):
    action: Literal["hide", "restore", "dismiss"]
