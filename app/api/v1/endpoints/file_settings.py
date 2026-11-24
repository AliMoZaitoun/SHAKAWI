from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.foundations import RetentionPreview, RetentionRun
from app.schemas.file_settings import (
    RetentionEnableInput,
    RetentionPolicyInput,
    UploadLimitsInput,
)
from app.services.access import require_permission
from app.services.audit import record_event
from app.services.file_policy import (
    DEFAULT_RETENTION_SCOPE,
    get_file_policy,
    upload_policy_data,
)
from app.services.retention import disable_retention, enable_retention, make_preview

router = APIRouter()
manage = require_permission("files.manage", global_only=True)


@router.get("/upload-policy")
def public_upload_policy(db: Session = Depends(get_db)):
    return upload_policy_data(db)


def _actor_user_id(actor):
    return actor.user.id if actor.user else None


def settings_data(db: Session):
    policy = get_file_policy(db)
    limits = upload_policy_data(db)
    return {
        **limits,
        "retention": {
            "enabled": policy.retention_enabled,
            "days": policy.retention_days,
            "scope": list(policy.retention_scope or DEFAULT_RETENTION_SCOPE),
            "policy_version": policy.retention_policy_version,
            "reviewed_at": policy.retention_reviewed_at,
        },
        "recent_runs": [{
            "id": row.id,
            "status": row.status,
            "files_scanned": row.files_scanned,
            "files_purged": row.files_purged,
            "bytes_purged": row.bytes_purged,
            "failures": row.failures,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
        } for row in db.query(RetentionRun).order_by(RetentionRun.id.desc()).limit(10)],
    }


@router.get("/admin/settings/files")
def read_file_settings(actor=Depends(manage), db: Session = Depends(get_db)):
    return settings_data(db)


@router.put("/admin/settings/files/limits")
def update_upload_limits(
    data: UploadLimitsInput,
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    policy = get_file_policy(db)
    policy.mime_limits = data.mime_limits
    policy.updated_by_user_id = _actor_user_id(actor)
    record_event(
        db, "file_policy.limits_updated", "file_policy", "1",
        actor_user_id=_actor_user_id(actor),
    )
    db.commit()
    return settings_data(db)


@router.put("/admin/settings/files/retention")
def update_retention_policy(
    data: RetentionPolicyInput,
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    policy = get_file_policy(db)
    policy.retention_days = data.retention_days
    policy.retention_scope = list(data.retention_scope)
    # Every policy change requires a fresh preview and explicit approval.
    policy.retention_enabled = False
    policy.retention_reviewed_at = None
    policy.retention_review_fingerprint = None
    policy.retention_policy_version += 1
    policy.updated_by_user_id = _actor_user_id(actor)
    db.query(RetentionPreview).delete(synchronize_session=False)
    record_event(
        db, "file_policy.retention_policy_updated", "file_policy", "1",
        actor_user_id=_actor_user_id(actor),
    )
    db.commit()
    return settings_data(db)


@router.post("/admin/settings/files/retention/preview")
def preview_retention(actor=Depends(manage), db: Session = Depends(get_db)):
    try:
        result = make_preview(db)
        record_event(
            db, "file_policy.retention_previewed", "file_policy", "1",
            actor_user_id=_actor_user_id(actor),
        )
        db.commit()
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/admin/settings/files/retention/enable")
def approve_retention(
    data: RetentionEnableInput,
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    try:
        result = enable_retention(
            db, data.preview_token, actor_user_id=_actor_user_id(actor),
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    record_event(
        db, "file_policy.retention_enabled", "file_policy", "1",
        actor_user_id=_actor_user_id(actor),
    )
    db.commit()
    return {**result, "settings": settings_data(db)}


@router.post("/admin/settings/files/retention/disable")
def pause_retention(actor=Depends(manage), db: Session = Depends(get_db)):
    result = disable_retention(db, actor_user_id=_actor_user_id(actor))
    record_event(
        db, "file_policy.retention_disabled", "file_policy", "1",
        actor_user_id=_actor_user_id(actor),
    )
    db.commit()
    return {**result, "settings": settings_data(db)}
