import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.branding import DEFAULT_BRAND_COLORS

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
INK = "#283128"
WHITE = "#ffffff"


def _luminance(value: str) -> float:
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    high, low = sorted((_luminance(first.lower()), _luminance(second.lower())), reverse=True)
    return (high + 0.05) / (low + 0.05)


class BrandColors(BaseModel):
    brand_dark: str = Field(default=DEFAULT_BRAND_COLORS["brand_dark"])
    brand_primary: str = Field(default=DEFAULT_BRAND_COLORS["brand_primary"])
    brand_light: str = Field(default=DEFAULT_BRAND_COLORS["brand_light"])
    brand_accent: str = Field(default=DEFAULT_BRAND_COLORS["brand_accent"])
    brand_gold: str = Field(default=DEFAULT_BRAND_COLORS["brand_gold"])
    brand_bg: str = Field(default=DEFAULT_BRAND_COLORS["brand_bg"])
    brand_card: str = Field(default=DEFAULT_BRAND_COLORS["brand_card"])
    sidebar_item_bg: str = Field(default=DEFAULT_BRAND_COLORS["sidebar_item_bg"])

    @field_validator(*DEFAULT_BRAND_COLORS.keys())
    @classmethod
    def validate_hex(cls, value: str):
        if not HEX_COLOR.fullmatch(value):
            raise ValueError("استخدم رمز لون بصيغة #RRGGBB فقط")
        return value.lower()

    @model_validator(mode="after")
    def ensure_readable_surfaces(self):
        if contrast_ratio(self.brand_dark, WHITE) < 4.5:
            raise ValueError("لون الهوية الداكن يحتاج تباينًا لا يقل عن 4.5 مع النص الأبيض")
        if contrast_ratio(self.brand_primary, WHITE) < 4.5:
            raise ValueError("اللون الأساسي يحتاج تباينًا لا يقل عن 4.5 مع النص الأبيض")
        if contrast_ratio(INK, self.brand_bg) < 4.5:
            raise ValueError("لون خلفية الموقع لا يحقق تباينًا كافيًا مع النص")
        if contrast_ratio(INK, self.brand_card) < 4.5:
            raise ValueError("لون البطاقات لا يحقق تباينًا كافيًا مع النص")
        return self


class BrandingInput(BaseModel):
    colors: BrandColors
    hero_art_style: Literal["flowing_lines", "architectural", "none"] | None = None
