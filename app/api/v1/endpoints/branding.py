from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from uuid import uuid4

from app.db.session import get_db
from app.schemas.branding import BrandingInput
from app.services.access import require_permission
from app.services.audit import record_event
from app.services.branding import (
    BRANDING_DIR,
    HERO_IMAGE_MAX_BYTES,
    UPLOAD_DIR,
    branding_data,
    get_brand_settings,
    remove_logo,
    safe_logo_path,
    sanitize_hero_image,
    sanitize_logo,
)

router = APIRouter()
manage = require_permission("branding.manage", global_only=True)


def _actor_id(actor):
    return actor.user.id if actor.user else None


def _settings(db):
    return branding_data(get_brand_settings(db))


@router.get("/branding")
def public_branding(db: Session = Depends(get_db)):
    return _settings(db)


@router.get("/branding/logo")
def public_logo(v: int | None = None, db: Session = Depends(get_db)):
    row = get_brand_settings(db)
    path = safe_logo_path(row.logo_path)
    if not path:
        raise HTTPException(404, "لا يوجد شعار مخصص")
    return FileResponse(
        path,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=300, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/branding/hero-image")
def public_hero_image(v: int | None = None, db: Session = Depends(get_db)):
    row = get_brand_settings(db)
    if not row.hero_image_data:
        raise HTTPException(404, "لا توجد صورة رئيسية مخصصة")
    return Response(
        content=row.hero_image_data,
        media_type=row.hero_image_mime or "image/jpeg",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/admin/settings/branding")
def read_branding(actor=Depends(manage), db: Session = Depends(get_db)):
    return _settings(db)


@router.put("/admin/settings/branding")
def save_branding(
    data: BrandingInput,
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    row = get_brand_settings(db)
    for key, value in data.colors.model_dump().items():
        setattr(row, key, value)
    if data.hero_art_style is not None:
        row.hero_art_style = data.hero_art_style
    row.updated_by_user_id = _actor_id(actor)
    record_event(
        db, "branding.colors_updated", "brand_settings", "1",
        actor_user_id=_actor_id(actor),
    )
    db.commit()
    return _settings(db)


@router.post("/admin/settings/branding/hero-image")
async def upload_brand_hero_image(
    file: UploadFile = File(...),
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    try:
        raw = await file.read(HERO_IMAGE_MAX_BYTES + 1)
        if len(raw) > HERO_IMAGE_MAX_BYTES:
            raise HTTPException(413, "حجم الصورة يجب ألا يتجاوز 8 ميغابايت")
        image_data, image_mime = sanitize_hero_image(raw, file.content_type)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(415, str(exc))
    finally:
        await file.close()

    row = get_brand_settings(db)
    row.hero_image_data = image_data
    row.hero_image_mime = image_mime
    row.hero_image_version += 1
    row.updated_by_user_id = _actor_id(actor)
    record_event(
        db, "branding.hero_image_updated", "brand_settings", "1",
        actor_user_id=_actor_id(actor),
    )
    db.commit()
    return _settings(db)


@router.delete("/admin/settings/branding/hero-image")
def reset_brand_hero_image(actor=Depends(manage), db: Session = Depends(get_db)):
    row = get_brand_settings(db)
    row.hero_image_data = None
    row.hero_image_mime = None
    row.hero_image_version += 1
    row.updated_by_user_id = _actor_id(actor)
    record_event(
        db, "branding.hero_image_reset", "brand_settings", "1",
        actor_user_id=_actor_id(actor),
    )
    db.commit()
    return _settings(db)


@router.post("/admin/settings/branding/logo")
async def upload_brand_logo(
    file: UploadFile = File(...),
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    try:
        raw = await file.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise HTTPException(413, "حجم الشعار يجب ألا يتجاوز 2 ميغابايت")
        logo = sanitize_logo(raw, file.content_type)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(415, str(exc))
    finally:
        await file.close()

    if UPLOAD_DIR.is_symlink():
        raise HTTPException(500, "مسار تخزين الشعار غير آمن")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if BRANDING_DIR.is_symlink():
        raise HTTPException(500, "مسار تخزين الشعار غير آمن")
    BRANDING_DIR.mkdir(exist_ok=True)
    root = BRANDING_DIR.resolve()
    if not root.is_relative_to(UPLOAD_DIR.resolve()):
        raise HTTPException(500, "مسار تخزين الشعار غير آمن")
    path = BRANDING_DIR / f"{uuid4().hex}.png"
    old_path = get_brand_settings(db).logo_path
    try:
        path.write_bytes(logo)
        row = get_brand_settings(db)
        row.logo_path = str(path)
        row.logo_version += 1
        row.updated_by_user_id = _actor_id(actor)
        record_event(
            db, "branding.logo_updated", "brand_settings", "1",
            actor_user_id=_actor_id(actor),
        )
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    remove_logo(old_path)
    return _settings(db)


@router.delete("/admin/settings/branding/logo")
def reset_brand_logo(actor=Depends(manage), db: Session = Depends(get_db)):
    row = get_brand_settings(db)
    old_path = row.logo_path
    row.logo_path = None
    row.logo_version += 1
    row.updated_by_user_id = _actor_id(actor)
    record_event(
        db, "branding.logo_reset", "brand_settings", "1",
        actor_user_id=_actor_id(actor),
    )
    db.commit()
    remove_logo(old_path)
    return _settings(db)
