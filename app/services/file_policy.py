"""Central, database-backed limits for the platform's fixed file allowlist."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.foundations import FilePolicy
from app.services.uploads import ALLOWED_TYPES, HARD_MAX_BYTES

RETENTION_SCOPES = {"complaint_files", "evidence_reply_files"}
DEFAULT_RETENTION_SCOPE = ["complaint_files", "evidence_reply_files"]
MIME_LABELS = {
    "image/jpeg": ("صورة JPEG", "JPEG image"),
    "image/png": ("صورة PNG", "PNG image"),
    "image/webp": ("صورة WebP", "WebP image"),
    "application/pdf": ("مستند PDF", "PDF document"),
    "audio/ogg": ("صوت OGG", "OGG audio"),
    "audio/mpeg": ("صوت MP3", "MP3 audio"),
    "audio/mp4": ("صوت M4A", "M4A audio"),
    "video/mp4": ("فيديو MP4", "MP4 video"),
}


def bootstrap_file_policy(db: Session) -> FilePolicy:
    policy = db.get(FilePolicy, 1)
    if policy is None:
        policy = FilePolicy(
            id=1,
            mime_limits={mime: HARD_MAX_BYTES for mime in ALLOWED_TYPES},
            retention_enabled=False,
            retention_days=30,
            retention_scope=list(DEFAULT_RETENTION_SCOPE),
            retention_policy_version=1,
        )
        db.add(policy)
        db.flush()
    return policy


def get_file_policy(db: Session) -> FilePolicy:
    return db.get(FilePolicy, 1) or bootstrap_file_policy(db)


def max_upload_bytes(db: Session, mime_type: str) -> int:
    if mime_type not in ALLOWED_TYPES:
        raise HTTPException(415, "نوع الملف غير مدعوم")
    policy = get_file_policy(db)
    limit = (policy.mime_limits or {}).get(mime_type)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= HARD_MAX_BYTES:
        raise RuntimeError(f"Invalid upload limit configured for {mime_type}")
    return limit


def upload_policy_data(db: Session) -> dict:
    policy = get_file_policy(db)
    return {
        "hard_max_bytes": HARD_MAX_BYTES,
        "mime_types": [
            {
                "mime_type": mime,
                "label_ar": MIME_LABELS[mime][0],
                "label_en": MIME_LABELS[mime][1],
                "max_bytes": max_upload_bytes(db, mime),
            }
            for mime in ALLOWED_TYPES
        ],
    }
