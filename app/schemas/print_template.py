import re

from pydantic import BaseModel, Field, field_validator

from app.services.print_templates import PRINT_SECTION_IDS


class PrintTemplateInput(BaseModel):
    titles: dict[str, str] = Field(min_length=1, max_length=20)
    default_sections: list[str] = Field(min_length=1, max_length=len(PRINT_SECTION_IDS))

    @field_validator("titles")
    @classmethod
    def validate_titles(cls, titles):
        valid_code = re.compile(r"^[a-z][a-z0-9_-]{0,34}$")
        for code, title in titles.items():
            if not valid_code.fullmatch(code):
                raise ValueError("رمز لغة غير صالح في عناوين الطباعة")
            if not isinstance(title, str) or len(title.strip()) > 120:
                raise ValueError("عنوان الطباعة يجب ألا يتجاوز 120 حرفًا")
        if not titles.get("ar", "").strip() or not titles.get("en", "").strip():
            raise ValueError("يجب توفير عنوان للطباعة بالعربية والإنجليزية")
        return {code: title.strip() for code, title in titles.items()}

    @field_validator("default_sections")
    @classmethod
    def validate_sections(cls, sections):
        if len(sections) != len(set(sections)):
            raise ValueError("لا يمكن تكرار قسم الطباعة")
        unknown = set(sections) - PRINT_SECTION_IDS
        if unknown:
            raise ValueError("يتضمن القالب قسمًا غير مسموح")
        return sections
