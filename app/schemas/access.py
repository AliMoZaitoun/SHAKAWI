"""React-facing administrative contracts, separate from legacy citizen DTOs."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CleanInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class RoleInput(CleanInput):
    code: str = Field(min_length=2, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=2000)
    permissions: list[str] = Field(default_factory=list, max_length=100)


class RoleUpdate(CleanInput):
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=2000)
    permissions: list[str] = Field(max_length=100)


class PermissionUpdate(CleanInput):
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=2000)


class DirectorateInput(CleanInput):
    name: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=4000)
    location: str = Field(default="", max_length=500)
    is_active: bool = True
    parent_id: int | None = Field(default=None, gt=0)


class AssignmentInput(CleanInput):
    role_id: int = Field(gt=0)
    scope_type: Literal["global", "directorate"]
    directorate_id: int | None = Field(default=None, gt=0)


class EmployeeInput(CleanInput):
    first_name: str = Field(min_length=2, max_length=50)
    last_name: str = Field(min_length=2, max_length=50)
    phone: str = Field(min_length=8, max_length=20, pattern=r"^\+?[0-9]+$")
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    username: str = Field(min_length=2, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    directorate_id: int | None = Field(default=None, gt=0)

    @field_validator("first_name", "last_name")
    @classmethod
    def name_without_digits(cls, value):
        if any(character.isdigit() for character in value):
            raise ValueError("الاسم يجب ألا يحتوي على أرقام")
        return value


class EmployeeUpdate(CleanInput):
    first_name: str = Field(min_length=2, max_length=50)
    last_name: str = Field(min_length=2, max_length=50)
    phone: str = Field(min_length=8, max_length=20, pattern=r"^\+?[0-9]+$")
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    directorate_id: int | None = Field(default=None, gt=0)
    is_active: bool

    @field_validator("first_name", "last_name")
    @classmethod
    def name_without_digits(cls, value):
        return EmployeeInput.name_without_digits(value)
