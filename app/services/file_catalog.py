"""One private catalog, explicit FK links, legacy IDs retained for old clients."""
import hashlib
import mimetypes
from pathlib import Path
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session
from app.models.complaint import Attachment, EvidenceFile
from app.models.user import Citizen
from app.models.foundations import StoredFile, ComplaintFile, CitizenFile, EvidenceReplyFile
from app.services.request_context import request_context
from app.services.uploads import UPLOAD_DIR


def catalog_file(conn, path, mime=None, name=None, user_id=None):
    table = StoredFile.__table__
    existing = conn.execute(select(table.c.id).where(table.c.storage_key == path)).scalar()
    if existing:
        return existing
    resolved = Path(path).resolve()
    size = checksum = None
    # Missing legacy bytes remain explicitly missing; never read outside uploads.
    if resolved.is_relative_to(UPLOAD_DIR.resolve()) and resolved.is_file():
        size = resolved.stat().st_size
        digest = hashlib.sha256()
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)
        checksum = digest.hexdigest()
    result = conn.execute(table.insert().values(
        storage_key=path, storage_disk="local", original_name=name or Path(path).name,
        mime_type=mime or mimetypes.guess_type(path)[0] or "application/octet-stream",
        size_bytes=size, checksum=checksum, uploaded_by_user_id=user_id,
    ))
    return result.inserted_primary_key[0]


def add_link(conn, table, values, lookup):
    if not conn.execute(select(table).filter_by(**lookup)).first():
        conn.execute(table.insert().values(**values))


def sync_file(conn, row, user_id=None):
    if isinstance(row, Attachment):
        file_id = catalog_file(conn, row.file_path, row.file_type,
                               getattr(row, "_original_name", None), user_id=user_id)
        if row.attachable_type in ("complaint", "complaints"):
            add_link(conn, ComplaintFile.__table__,
                     dict(file_id=file_id, complaint_id=row.attachable_id, legacy_attachment_id=row.id),
                     dict(legacy_attachment_id=row.id))
        elif row.attachable_type in ("citizen", "citizens"):
            add_link(conn, CitizenFile.__table__, dict(file_id=file_id, citizen_id=row.attachable_id,
                     purpose="attachment", is_current=True), dict(file_id=file_id, citizen_id=row.attachable_id))
        else:
            raise ValueError("Unsupported legacy attachment owner; migration stopped without deleting it")
    elif isinstance(row, EvidenceFile):
        file_id = catalog_file(conn, row.file_path, row.file_type, row.name, user_id)
        add_link(conn, EvidenceReplyFile.__table__,
                 dict(file_id=file_id, reply_id=row.reply_id, legacy_evidence_file_id=row.id),
                 dict(legacy_evidence_file_id=row.id))
    elif isinstance(row, Citizen) and row.identity_card_url:
        file_id = catalog_file(conn, row.identity_card_url,
                               name=getattr(row, "_identity_original_name", None), user_id=user_id)
        conn.execute(update(CitizenFile).where(CitizenFile.citizen_id == row.id,
                     CitizenFile.purpose == "identity").values(is_current=False))
        table = CitizenFile.__table__
        if conn.execute(select(table).filter_by(file_id=file_id, citizen_id=row.id)).first():
            conn.execute(table.update().filter_by(file_id=file_id, citizen_id=row.id).values(is_current=True))
        else:
            conn.execute(table.insert().values(file_id=file_id, citizen_id=row.id, purpose="identity", is_current=True))


def backfill_files(db):
    conn = db.connection()
    for model in (Attachment, EvidenceFile, Citizen):
        for row in db.query(model):
            sync_file(conn, row)


@event.listens_for(Session, "before_flush")
def capture_files(db, context, instances):
    from sqlalchemy import inspect
    for row in list(db.new) + list(db.dirty):
        if row in db.deleted:
            continue
        if isinstance(row, (Attachment, EvidenceFile)) or (
            isinstance(row, Citizen) and (row in db.new or inspect(row).attrs.identity_card_url.history.has_changes())
        ):
            db.info.setdefault("catalog_pending", []).append(row)


@event.listens_for(Session, "after_flush_postexec")
def flush_files(db, context):
    for row in db.info.pop("catalog_pending", []):
        sync_file(db.connection(), row, request_context.get().get("actor_user_id"))


@event.listens_for(Session, "after_rollback")
def clear_pending(db):
    for key in ("catalog_pending", "arabic_translations", "audit_pending"):
        db.info.pop(key, None)


def protected_path(file):
    from fastapi import HTTPException
    path = Path(file.storage_key).resolve()
    if file.storage_disk != "local" or not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
        raise HTTPException(404, "الملف غير موجود في التخزين")
    return path
