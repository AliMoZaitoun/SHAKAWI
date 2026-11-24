from pydantic import BaseModel, ConfigDict, Field


class ComplaintTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=50)
    description: str = Field(default="", max_length=4000)
    sla_duration_minutes: int = Field(gt=0, le=5_256_000)


class ComplaintTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=50)
    description: str = Field(default="", max_length=4000)
    sla_duration_minutes: int | None = Field(default=None, gt=0, le=5_256_000)
    is_active: bool = True
