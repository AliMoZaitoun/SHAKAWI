"""Reviewed, idempotent deletion of file bytes only; metadata remains auditable."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
from secrets import token_urlsafe

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.complaint import Complaint, StatusEnum
from app.models.foundations import (
    CitizenFile,
    ComplaintFile,
    EvidenceReplyFile,
    FilePolicy,
    RetentionPreview,
    RetentionRun,
    StoredFile,
)
from app.models.complaint import EvidenceReply, EvidenceRequest
from app.services.file_catalog import UPLOAD_DIR
from app.services.file_policy import get_file_policy

logger = logging.getLogger("file_retention")
PREVIEW_TTL = timedelta(minutes=10)
RUNNING_GRACE = timedelta(hours=2)


def _citizen_files_excluded(db):
    return ~select(CitizenFile.file_id).where(
        CitizenFile.file_id == StoredFile.id,
    ).exists()


def _candidate_rows(db: Session, policy: FilePolicy, cutoff: datetime):
    scopes = set(policy.retention_scope or [])
    rows = {}
    age_filter = or_(StoredFile.created_at.is_(None), StoredFile.created_at <= cutoff)
    citizen_file_filter = _citizen_files_excluded(db)

    if "complaint_files" in scopes:
        query = db.query(
            StoredFile.id,
            StoredFile.size_bytes,
            Complaint.id,
            Complaint.tracking_code,
            Complaint.resolved_at,
        ).join(ComplaintFile, ComplaintFile.file_id == StoredFile.id).join(
            Complaint, Complaint.id == ComplaintFile.complaint_id,
        ).filter(
            Complaint.status == StatusEnum.RESOLVED,
            Complaint.resolved_at.is_not(None),
            Complaint.resolved_at <= cutoff,
            StoredFile.purged_at.is_(None),
            age_filter,
            citizen_file_filter,
        )
        for file_id, size, complaint_id, code, resolved_at in query.all():
            rows.setdefault(file_id, {
                "id": file_id, "size_bytes": size or 0,
                "complaints": {}, "scopes": set(),
            })["complaints"][complaint_id] = (code, resolved_at)
            rows[file_id]["scopes"].add("complaint_files")

    if "evidence_reply_files" in scopes:
        query = db.query(
            StoredFile.id,
            StoredFile.size_bytes,
            Complaint.id,
            Complaint.tracking_code,
            Complaint.resolved_at,
        ).join(EvidenceReplyFile, EvidenceReplyFile.file_id == StoredFile.id).join(
            EvidenceReply, EvidenceReply.id == EvidenceReplyFile.reply_id,
        ).join(EvidenceRequest, EvidenceRequest.id == EvidenceReply.request_id).join(
            Complaint, Complaint.id == EvidenceRequest.complaint_id,
        ).filter(
            Complaint.status == StatusEnum.RESOLVED,
            Complaint.resolved_at.is_not(None),
            Complaint.resolved_at <= cutoff,
            StoredFile.purged_at.is_(None),
            age_filter,
            citizen_file_filter,
        )
        for file_id, size, complaint_id, code, resolved_at in query.all():
            rows.setdefault(file_id, {
                "id": file_id, "size_bytes": size or 0,
                "complaints": {}, "scopes": set(),
            })["complaints"][complaint_id] = (code, resolved_at)
            rows[file_id]["scopes"].add("evidence_reply_files")
    if not rows:
        return rows

    candidate_ids = list(rows)
    all_scopes = {file_id: set() for file_id in candidate_ids}
    all_complaints = {file_id: set() for file_id in candidate_ids}
    citizen_files = {
        file_id for (file_id,) in db.query(CitizenFile.file_id).filter(
            CitizenFile.file_id.in_(candidate_ids),
        ).all()
    }
    for file_id, complaint_id in db.query(
        ComplaintFile.file_id, ComplaintFile.complaint_id,
    ).filter(ComplaintFile.file_id.in_(candidate_ids)).all():
        all_scopes[file_id].add("complaint_files")
        all_complaints[file_id].add(complaint_id)
    evidence_links = db.query(
        EvidenceReplyFile.file_id, Complaint.id,
    ).join(EvidenceReply, EvidenceReply.id == EvidenceReplyFile.reply_id).join(
        EvidenceRequest, EvidenceRequest.id == EvidenceReply.request_id,
    ).join(Complaint, Complaint.id == EvidenceRequest.complaint_id).filter(
        EvidenceReplyFile.file_id.in_(candidate_ids),
    ).all()
    for file_id, complaint_id in evidence_links:
        all_scopes[file_id].add("evidence_reply_files")
        all_complaints[file_id].add(complaint_id)

    for file_id, row in list(rows.items()):
        if (
            file_id in citizen_files
            or not all_scopes[file_id].issubset(scopes)
            or not all_scopes[file_id].issubset(row["scopes"])
            or not all_complaints[file_id].issubset(row["complaints"])
        ):
            rows.pop(file_id)
    return rows


def _fingerprint(policy, cutoff, rows):
    normalized_cutoff = (
        cutoff.replace(tzinfo=timezone.utc)
        if cutoff.tzinfo is None
        else cutoff.astimezone(timezone.utc)
    )
    content = {
        "version": policy.retention_policy_version,
        "days": policy.retention_days,
        "scope": sorted(policy.retention_scope or []),
        "cutoff": normalized_cutoff.isoformat(),
        "files": [
            (row["id"], row["size_bytes"], sorted(row["complaints"]), sorted(row["scopes"]))
            for row in sorted(rows.values(), key=lambda item: item["id"])
        ],
    }
    return hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _preview_groups(rows):
    grouped = {}
    for row in rows.values():
        for complaint_id, (code, resolved_at) in row["complaints"].items():
            item = grouped.setdefault(complaint_id, {
                "tracking_code": code,
                "resolved_at": resolved_at,
                "file_count": 0,
                "bytes_total": 0,
            })
            item["file_count"] += 1
            item["bytes_total"] += row["size_bytes"]
    return sorted(grouped.values(), key=lambda item: item["tracking_code"])


def make_preview(db: Session, *, now=None):
    now = now or datetime.now(timezone.utc)
    policy = get_file_policy(db)
    if not policy.retention_days or not policy.retention_scope:
        raise ValueError("حدد مدة الاحتفاظ ونطاق الملفات أولًا")
    db.query(RetentionPreview).filter(RetentionPreview.expires_at <= now).delete(
        synchronize_session=False,
    )
    cutoff = now - timedelta(days=policy.retention_days)
    rows = _candidate_rows(db, policy, cutoff)
    fingerprint = _fingerprint(policy, cutoff, rows)
    token = token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = now + PREVIEW_TTL
    db.add(RetentionPreview(
        token_hash=token_hash,
        policy_version=policy.retention_policy_version,
        cutoff_at=cutoff,
        expires_at=expires_at,
        candidate_fingerprint=fingerprint,
        file_count=len(rows),
        bytes_total=sum(row["size_bytes"] for row in rows.values()),
    ))
    db.commit()
    return {
        "preview_token": token,
        "expires_at": expires_at,
        "cutoff_at": cutoff,
        "days": policy.retention_days,
        "scope": list(policy.retention_scope or []),
        "file_count": len(rows),
        "bytes_total": sum(row["size_bytes"] for row in rows.values()),
        "complaints": _preview_groups(rows),
        "includes_identity_files": False,
        "preserves_complaint_and_audit_history": True,
    }


def enable_retention(db: Session, token: str, *, actor_user_id=None, now=None):
    now = now or datetime.now(timezone.utc)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    preview = db.get(RetentionPreview, token_hash)
    policy = get_file_policy(db)
    if not preview or preview.expires_at.replace(tzinfo=timezone.utc) < now:
        raise ValueError("انتهت صلاحية المعاينة؛ أنشئ معاينة جديدة")
    if preview.policy_version != policy.retention_policy_version:
        raise ValueError("تغيرت إعدادات الاحتفاظ؛ أنشئ معاينة جديدة")
    rows = _candidate_rows(db, policy, preview.cutoff_at)
    if _fingerprint(policy, preview.cutoff_at, rows) != preview.candidate_fingerprint:
        raise ValueError("تغيرت الملفات المتأثرة؛ راجع معاينة جديدة قبل التفعيل")
    policy.retention_enabled = True
    policy.retention_reviewed_at = now
    policy.retention_review_fingerprint = preview.candidate_fingerprint
    policy.updated_by_user_id = actor_user_id
    db.delete(preview)
    db.commit()
    return {
        "retention_enabled": True,
        "retention_days": policy.retention_days,
        "retention_scope": list(policy.retention_scope or []),
        "message": "تم تفعيل السياسة بعد مراجعة المعاينة؛ التنفيذ المجدول يبدأ في موعده اليومي التالي.",
    }


def disable_retention(db: Session, *, actor_user_id=None):
    policy = get_file_policy(db)
    policy.retention_enabled = False
    policy.retention_reviewed_at = None
    policy.retention_review_fingerprint = None
    policy.retention_policy_version += 1
    policy.updated_by_user_id = actor_user_id
    db.query(RetentionPreview).delete(synchronize_session=False)
    db.commit()
    return {"retention_enabled": False, "message": "تم إيقاف الحذف الدوري."}


def _safe_local_path(storage_key):
    root = UPLOAD_DIR.resolve()
    stored = Path(storage_key)
    if stored.is_absolute():
        candidate = stored
    else:
        relative = stored
        if relative.parts and relative.parts[0] == UPLOAD_DIR.name:
            relative = Path(*relative.parts[1:])
        candidate = root / relative
    path = Path(os.path.abspath(candidate))
    if not path.is_relative_to(root):
        return None
    # Never follow a symlink to another stored file or outside the upload root.
    current = path
    while current != root:
        if current.is_symlink():
            return None
        current = current.parent
    return path


def _is_still_eligible(db: Session, file: StoredFile, policy: FilePolicy, cutoff: datetime):
    if file.purged_at is not None or not policy.retention_enabled:
        return False
    if file.storage_disk != "local":
        return False
    if file.created_at is not None:
        file_created = (
            file.created_at.replace(tzinfo=timezone.utc)
            if file.created_at.tzinfo is None
            else file.created_at.astimezone(timezone.utc)
        )
        normalized_cutoff = (
            cutoff.replace(tzinfo=timezone.utc)
            if cutoff.tzinfo is None
            else cutoff.astimezone(timezone.utc)
        )
        if file_created > normalized_cutoff:
            return False
    if db.query(CitizenFile.file_id).filter_by(file_id=file.id).first():
        return False

    scopes = set(policy.retention_scope or [])
    direct = db.query(Complaint.status, Complaint.resolved_at).join(
        ComplaintFile, ComplaintFile.complaint_id == Complaint.id,
    ).filter(ComplaintFile.file_id == file.id).all()
    evidence = db.query(Complaint.status, Complaint.resolved_at).join(
        EvidenceRequest, EvidenceRequest.complaint_id == Complaint.id,
    ).join(EvidenceReply, EvidenceReply.request_id == EvidenceRequest.id).join(
        EvidenceReplyFile, EvidenceReplyFile.reply_id == EvidenceReply.id,
    ).filter(EvidenceReplyFile.file_id == file.id).all()
    owners = []
    if direct:
        if "complaint_files" not in scopes:
            return False
        owners.extend(direct)
    if evidence:
        if "evidence_reply_files" not in scopes:
            return False
        owners.extend(evidence)
    if not owners:
        return False
    normalized_cutoff = (
        cutoff.replace(tzinfo=timezone.utc)
        if cutoff.tzinfo is None
        else cutoff.astimezone(timezone.utc)
    )
    for status, resolved_at in owners:
        if status != StatusEnum.RESOLVED or resolved_at is None:
            return False
        resolved_at = (
            resolved_at.replace(tzinfo=timezone.utc)
            if resolved_at.tzinfo is None
            else resolved_at.astimezone(timezone.utc)
        )
        if resolved_at > normalized_cutoff:
            return False
    return True


def run_retention(session_factory, *, now=None):
    """Purge only eligible bytes. Re-running the same day is safe and idempotent."""
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    with session_factory() as db:
        policy = get_file_policy(db)
        if (not policy.retention_enabled or policy.retention_reviewed_at is None
                or not policy.retention_review_fingerprint):
            return {"status": "disabled", "files_purged": 0, "bytes_purged": 0}
        policy_version = policy.retention_policy_version
        run_key = f"{day}:{policy_version}"
        run = db.query(RetentionRun).filter_by(run_key=run_key).first()
        if run and run.status == "completed":
            return {
                "status": "completed", "files_purged": run.files_purged,
                "bytes_purged": run.bytes_purged,
            }
        if run and run.status == "running":
            started = run.started_at
            if started and started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if started and now - started < RUNNING_GRACE:
                return {"status": "already_running", "files_purged": 0, "bytes_purged": 0}
        if run is None:
            run = RetentionRun(
                run_key=run_key, policy_version=policy_version, status="running",
            )
            db.add(run)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                return {"status": "already_running", "files_purged": 0, "bytes_purged": 0}
        else:
            run.status = "running"
            db.commit()
        cutoff = now - timedelta(days=policy.retention_days)
        file_ids = sorted(_candidate_rows(db, policy, cutoff))
        run_id = run.id
        run.files_scanned = len(file_ids)
        db.commit()

    purged = bytes_purged = failures = 0
    for file_id in file_ids:
        with session_factory() as db:
            current_policy = get_file_policy(db)
            if (
                not current_policy.retention_enabled
                or current_policy.retention_policy_version != policy_version
            ):
                failures += 1
                break
            file = db.get(StoredFile, file_id)
            if file is None or not _is_still_eligible(db, file, current_policy, cutoff):
                continue
            path = _safe_local_path(file.storage_key) if file.storage_disk == "local" else None
            if path is None:
                failures += 1
                continue
            try:
                actual_size = path.stat().st_size if path.is_file() else 0
                if path.exists():
                    if not path.is_file():
                        failures += 1
                        continue
                    path.unlink()
                file.purged_at = now
                db.commit()
                purged += 1
                bytes_purged += actual_size
            except OSError:
                db.rollback()
                failures += 1

    with session_factory() as db:
        run = db.get(RetentionRun, run_id)
        run.files_purged = purged
        run.bytes_purged = bytes_purged
        run.failures = failures
        run.status = "partial" if failures else "completed"
        run.finished_at = now
        from app.services.audit import record_event
        record_event(
            db,
            "retention.run_partial" if failures else "retention.run_completed",
            "retention_run",
            run.id,
        )
        db.commit()
    logger.info(
        "Retention run finished: files_scanned=%s files_purged=%s bytes_purged=%s failures=%s",
        len(file_ids), purged, bytes_purged, failures,
    )
    return {
        "status": "partial" if failures else "completed",
        "files_scanned": len(file_ids),
        "files_purged": purged,
        "bytes_purged": bytes_purged,
        "failures": failures,
    }


async def retention_scheduler(session_factory):
    while True:
        now = datetime.now(timezone.utc)
        next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await asyncio.sleep(max(1, (next_run - now).total_seconds()))
        try:
            await asyncio.to_thread(run_retention, session_factory)
        except Exception:
            # Never include file paths, filenames, or citizen data in scheduler logs.
            logger.error("Scheduled retention run failed; files were not confirmed as purged.")
