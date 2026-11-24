from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.uploads import ALLOWED_TYPES, HARD_MAX_BYTES


class UploadLimitsInput(BaseModel):
    mime_limits: dict[str, int]

    @model_validator(mode="after")
    def validate_fixed_allowlist(self):
        if set(self.mime_limits) != set(ALLOWED_TYPES):
            raise ValueError("لا يمكن إضافة أو إزالة أنواع الملفات المدعومة")
        if any(isinstance(value, bool) or not 1 <= value <= HARD_MAX_BYTES
               for value in self.mime_limits.values()):
            raise ValueError("يجب أن يكون الحد بين بايت واحد و10 ميغابايت")
        return self


class RetentionPolicyInput(BaseModel):
    retention_days: int = Field(ge=1, le=3650)
    retention_scope: list[Literal["complaint_files", "evidence_reply_files"]] = Field(
        min_length=1, max_length=2,
    )

    @model_validator(mode="after")
    def validate_unique_scope(self):
        if len(self.retention_scope) != len(set(self.retention_scope)):
            raise ValueError("لا تكرر نطاق الملفات")
        return self


class RetentionEnableInput(BaseModel):
    preview_token: str = Field(min_length=32, max_length=100)
