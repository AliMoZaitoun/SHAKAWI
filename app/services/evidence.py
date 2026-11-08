"""Private evidence serialization and validated, non-public storage."""
import hashlib
import io
import json
import re
import warnings
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader

from app.services.uploads import UPLOAD_DIR, MAX_BYTES

Image.MAX_IMAGE_PIXELS = 20_000_000

TYPES = {"JPEG": ("image/jpeg", ".jpg"), "PNG": ("image/png", ".png"),
         "WEBP": ("image/webp", ".webp"), "PDF": ("application/pdf", ".pdf")}


def reply_data(reply):
    from sqlalchemy.orm import object_session
    from app.models.foundations import EvidenceReplyFile
    db = object_session(reply)
    links = {row.legacy_evidence_file_id: row.file_id for row in db.query(
        EvidenceReplyFile).filter_by(reply_id=reply.id)} if db else {}
    return {"id": reply.id, "text": reply.text, "channel": reply.channel,
            "created_at": reply.created_at,
            "attachments": [{"id": f.id, "file_id": links.get(f.id), "name": f.name, "file_type": f.file_type,
                             "file_url": f"/api/v1/files/{links[f.id]}/download" if f.id in links else
                             f"/api/v1/evidence-files/{f.id}/download"}
                            for f in reply.attachments]}


def request_data(row, staff=False):
    data = {"id": row.id, "complaint_id": row.complaint_id, "prompt": row.prompt,
            "author_name": row.author.full_name if row.author else "موظف",
            "created_at": row.created_at, "status": row.status,
            "replies": [reply_data(r) for r in row.replies]}
    if staff:
        data.update(notification_status=row.notification_status,
                    notification_error=row.notification_error)
    return data


async def validate_files(files):
    if len(files) > 5:
        raise HTTPException(422, "يسمح بخمسة ملفات كحد أقصى لكل رد")
    validated = []
    try:
        for file in files:
            name = file.filename or "ملف"
            if len(name) > 120 or "/" in name or "\\" in name or any(ord(c) < 32 for c in name):
                raise HTTPException(422, "اسم الملف غير صالح")
            raw = await file.read(MAX_BYTES + 1)
            if not raw or len(raw) > MAX_BYTES:
                raise HTTPException(413, f"{name}: الملف فارغ أو يتجاوز 10 ميغابايت")
            kind = None
            try:
                if raw.startswith(b"%PDF-"):
                    pdf = PdfReader(io.BytesIO(raw), strict=True)
                    if pdf.is_encrypted or not pdf.pages:
                        raise ValueError("encrypted or empty")
                    # Reject active PDF features; downloads are still attachment-only.
                    if re.search(rb"/(?:JavaScript|JS|Launch|EmbeddedFiles|OpenAction|AA)\b", raw):
                        raise ValueError("active PDF")
                    kind = "PDF"
                else:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", Image.DecompressionBombWarning)
                        with Image.open(io.BytesIO(raw)) as image:
                            kind = image.format
                            image.verify()
                        with Image.open(io.BytesIO(raw)) as image:
                            image.load()
                mime, suffix = TYPES[kind]
            except Exception:
                raise HTTPException(415, f"{name}: المحتوى ليس صورة JPEG/PNG/WebP أو PDF صالحًا")
            if file.content_type != mime or Path(name).suffix.lower() not in {
                suffix, ".jpeg" if kind == "JPEG" else suffix
            }:
                raise HTTPException(415, f"{name}: امتداد الملف ونوعه لا يطابقان محتواه")
            validated.append((name, mime, suffix, raw))
    finally:
        for file in files:
            await file.close()
    return validated


def payload_digest(text, files):
    values = [text, [(name, mime, hashlib.sha256(raw).hexdigest())
                     for name, mime, _, raw in files]]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def store_file(suffix, raw):
    directory = UPLOAD_DIR / "evidence"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (uuid4().hex + suffix)
    try:
        path.write_bytes(raw)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return str(path)
