"""Public theme data and isolated, sanitized site-logo storage."""
import io
import os
from pathlib import Path
import warnings
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.models.foundations import BrandSettings
from app.services.uploads import UPLOAD_DIR

DEFAULT_BRAND_COLORS = {
    "brand_dark": "#3b4b32",
    "brand_primary": "#4a5d3f",
    "brand_light": "#657b57",
    "brand_accent": "#b88d4b",
    "brand_gold": "#d4a860",
    "brand_bg": "#f7f8f4",
    "brand_card": "#ffffff",
    "sidebar_item_bg": "#edf1e8",
}
DEFAULT_HERO_ART_STYLE = "flowing_lines"
LOGO_MAX_BYTES = 2 * 1024 * 1024
LOGO_MAX_PIXELS = 4_000_000
LOGO_MAX_EDGE = 4096
ALLOWED_LOGO_FORMATS = {"JPEG", "PNG", "WEBP"}
HERO_IMAGE_MAX_BYTES = 8 * 1024 * 1024
HERO_IMAGE_MAX_PIXELS = 16_000_000
HERO_IMAGE_MAX_EDGE = 5000
HERO_IMAGE_OUTPUT_MAX_BYTES = 8 * 1024 * 1024
ALLOWED_HERO_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
BRANDING_DIR = UPLOAD_DIR / "branding"


def bootstrap_brand_settings(db: Session) -> BrandSettings:
    row = db.get(BrandSettings, 1)
    if row is None:
        row = BrandSettings(
            id=1,
            **DEFAULT_BRAND_COLORS,
            hero_art_style=DEFAULT_HERO_ART_STYLE,
        )
        db.add(row)
        db.flush()
    return row


def get_brand_settings(db: Session) -> BrandSettings:
    return db.get(BrandSettings, 1) or bootstrap_brand_settings(db)


def color_data(row: BrandSettings) -> dict:
    return {key: getattr(row, key) for key in DEFAULT_BRAND_COLORS}


def branding_data(row: BrandSettings) -> dict:
    logo_path = safe_logo_path(row.logo_path)
    return {
        "colors": color_data(row),
        "hero_art_style": row.hero_art_style or DEFAULT_HERO_ART_STYLE,
        "hero_image_url": (
            f"/api/v1/branding/hero-image?v={row.hero_image_version}"
            if row.hero_image_data else None
        ),
        "logo_url": (
            f"/api/v1/branding/logo?v={row.logo_version}"
            if logo_path else None
        ),
        "logo_version": row.logo_version,
        "updated_at": row.updated_at,
    }


def safe_logo_path(storage_key: str | None) -> Path | None:
    if not storage_key:
        return None
    root = BRANDING_DIR.resolve()
    candidate = Path(storage_key)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    # Resolve the parent only. Never follow a logo symlink.
    candidate = Path(os.path.abspath(candidate))
    if not candidate.is_relative_to(root) or candidate.is_symlink() or not candidate.is_file():
        return None
    current = candidate.parent
    while current != root:
        if current.is_symlink():
            return None
        current = current.parent
    return candidate


def sanitize_logo(raw: bytes, declared_mime: str | None) -> bytes:
    if not raw:
        raise ValueError("ملف الشعار فارغ")
    if len(raw) > LOGO_MAX_BYTES:
        raise ValueError("حجم الشعار يجب ألا يتجاوز 2 ميغابايت")
    if declared_mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("يُقبل شعار PNG أو JPEG أو WebP فقط")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ALLOWED_LOGO_FORMATS:
                    raise ValueError("محتوى الصورة غير مدعوم")
                if (
                    image.width < 1 or image.height < 1
                    or image.width > LOGO_MAX_EDGE or image.height > LOGO_MAX_EDGE
                    or image.width * image.height > LOGO_MAX_PIXELS
                ):
                    raise ValueError("أبعاد الشعار أكبر من الحد المسموح")
                expected_mime = {
                    "JPEG": "image/jpeg",
                    "PNG": "image/png",
                    "WEBP": "image/webp",
                }[image.format]
                if declared_mime != expected_mime:
                    raise ValueError("امتداد الشعار ونوع محتواه غير متطابقين")
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ALLOWED_LOGO_FORMATS:
                    raise ValueError("محتوى الصورة غير مدعوم")
                image.load()
                image = ImageOps.exif_transpose(image)
                mode = "RGBA" if "A" in image.getbands() else "RGB"
                clean = image.convert(mode)
                output = io.BytesIO()
                clean.save(output, format="PNG", optimize=True)
    except ValueError:
        raise
    except Exception:
        raise ValueError("تعذر قراءة الشعار؛ ارفع صورة PNG أو JPEG أو WebP صالحة")
    sanitized = output.getvalue()
    if len(sanitized) > 5 * 1024 * 1024:
        raise ValueError("حجم الشعار بعد التحقق أكبر من الحد المسموح")
    return sanitized


def sanitize_hero_image(raw: bytes, declared_mime: str | None) -> tuple[bytes, str]:
    """Validate and re-encode a public homepage photo without retaining metadata."""
    if not raw:
        raise ValueError("ملف الصورة فارغ")
    if len(raw) > HERO_IMAGE_MAX_BYTES:
        raise ValueError("حجم الصورة يجب ألا يتجاوز 8 ميغابايت")
    if declared_mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("يُقبل JPEG أو PNG أو WebP فقط")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ALLOWED_HERO_IMAGE_FORMATS:
                    raise ValueError("محتوى الصورة غير مدعوم")
                if (
                    image.width < 1 or image.height < 1
                    or image.width > HERO_IMAGE_MAX_EDGE
                    or image.height > HERO_IMAGE_MAX_EDGE
                    or image.width * image.height > HERO_IMAGE_MAX_PIXELS
                ):
                    raise ValueError("أبعاد الصورة أكبر من الحد المسموح")
                expected_mime = {
                    "JPEG": "image/jpeg",
                    "PNG": "image/png",
                    "WEBP": "image/webp",
                }[image.format]
                if declared_mime != expected_mime:
                    raise ValueError("امتداد الصورة ونوع محتواها غير متطابقين")
                if getattr(image, "is_animated", False):
                    raise ValueError("ارفع صورة ثابتة، لا صورة متحركة")
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
                clean_image = ImageOps.exif_transpose(image)
                clean_image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                keep_alpha = "A" in clean_image.getbands() or "transparency" in clean_image.info
                output = io.BytesIO()
                if keep_alpha:
                    clean_image.convert("RGBA").save(output, format="PNG", optimize=True)
                    sanitized_mime = "image/png"
                else:
                    clean_image.convert("RGB").save(
                        output, format="JPEG", quality=88, optimize=True, progressive=True,
                    )
                    sanitized_mime = "image/jpeg"
    except ValueError:
        raise
    except Exception:
        raise ValueError("تعذر قراءة الصورة؛ ارفع ملف JPEG أو PNG أو WebP صالحًا")
    sanitized = output.getvalue()
    if len(sanitized) > HERO_IMAGE_OUTPUT_MAX_BYTES:
        raise ValueError("حجم الصورة بعد التجهيز يتجاوز الحد المسموح")
    return sanitized, sanitized_mime


def remove_logo(storage_key: str | None):
    path = safe_logo_path(storage_key)
    if path:
        path.unlink(missing_ok=True)
