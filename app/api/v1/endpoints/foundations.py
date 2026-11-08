"""Private files/history and global audit. No public file-serving mount."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.foundations import (
    StoredFile, ComplaintFile, CitizenFile, EvidenceReplyFile, AuditEvent, ComplaintHistory,
)
from app.models.complaint import Complaint, EvidenceReply, EvidenceRequest
from app.services.access import require_permission, check_permission
from app.services.file_catalog import protected_path
from app.services.access_admin import directorate_or_422
from app.core.security import (
    current_employee, authorize_reader, authorize_owner, authorize_complaint,
    owns_citizen, is_bot, require_bot_owner,
)

router = APIRouter()


def complaint_row(db, identifier):
    row = db.get(Complaint, identifier)
    if not row:
        raise HTTPException(404, "الشكوى غير موجودة")
    return row


@router.get("/files/{identifier}/download")
def download(identifier: int, request: Request, db: Session = Depends(get_db)):
    file = db.get(StoredFile, identifier)
    if not file:
        raise HTTPException(404, "الملف غير موجود")
    # Identity association is restrictive even if bytes were also attached elsewhere.
    identity_links = db.query(CitizenFile).filter_by(file_id=identifier, purpose="identity").all()
    if identity_links:
        allowed = False
        for link in identity_links:
            if is_bot(request):
                require_bot_owner(request, db, link.citizen_id)
                allowed = True
                break
            if owns_citizen(request, link.citizen_id):
                allowed = True
                break
        if not allowed:
            check_permission(current_employee(request, db), "files.identity.read", global_only=True)
    else:
        links = db.query(ComplaintFile).filter_by(file_id=identifier).all()
        evidence_links = db.query(EvidenceReplyFile).filter_by(file_id=identifier).all()
        if not links and not evidence_links:
            raise HTTPException(404, "لا توجد علاقة قابلة للوصول للملف")
        authorized = False
        for link in links:
            complaint = complaint_row(db, link.complaint_id)
            try:
                if request.session.get("employee_id") and not is_bot(request):
                    authorize_complaint(current_employee(request, db), complaint, "complaints.files.read")
                else:
                    authorize_owner(request, db, complaint)
                authorized = True
                break
            except HTTPException:
                continue
        if not authorized:
            for link in evidence_links:
                reply = db.get(EvidenceReply, link.reply_id)
                evidence = db.get(EvidenceRequest, reply.request_id)
                complaint = complaint_row(db, evidence.complaint_id)
                try:
                    authorize_reader(request, db, complaint)
                    if request.session.get("employee_id") and not is_bot(request):
                        authorize_complaint(current_employee(request, db), complaint, "evidence.files.read")
                    authorized = True
                    break
                except HTTPException:
                    continue
        if not authorized:
            raise HTTPException(403, "لا تملك صلاحية تنزيل الملف")
    path = protected_path(file)
    return FileResponse(path, filename=file.original_name, media_type="application/octet-stream")


@router.get("/admin/audit-events")
def audit_events(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                 action: str | None = None, entity_type: str | None = None,
                 actor=Depends(require_permission("audit.view", global_only=True)),
                 db: Session = Depends(get_db)):
    query = db.query(AuditEvent)
    if action:
        query = query.filter_by(action=action)
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    total = query.count()
    return {"total": total, "page": page, "items": [
        {key: getattr(row, key) for key in (
            "id", "actor_user_id", "action", "entity_type", "entity_id", "changes",
            "source", "request_id", "created_at",
        )} for row in query.order_by(AuditEvent.id.desc()).offset((page - 1) * page_size).limit(page_size)]}


@router.get("/complaints/{identifier}/history")
def history(identifier: int, request: Request, page: int = Query(1, ge=1),
            page_size: int = Query(25, ge=1, le=100), db: Session = Depends(get_db)):
    complaint = complaint_row(db, identifier)
    authorize_reader(request, db, complaint)
    staff = bool(request.session.get("employee_id")) and not is_bot(request)
    query = db.query(ComplaintHistory).filter_by(complaint_id=identifier)
    fields = ["id", "event", "old_status", "new_status", "old_directorate_id",
              "new_directorate_id", "old_progress", "new_progress", "created_at"]
    if staff:
        fields += ["actor_user_id", "reason", "source", "request_id"]
    return {"total": query.count(), "page": page, "items": [
        {key: getattr(row, key) for key in fields}
        for row in query.order_by(ComplaintHistory.id).offset((page - 1) * page_size).limit(page_size)]}


class TransferInput(BaseModel):
    directorate_id: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/complaints/{identifier}/transfer")
def transfer(identifier: int, data: TransferInput, actor=Depends(current_employee),
             db: Session = Depends(get_db)):
    complaint = complaint_row(db, identifier)
    authorize_complaint(actor, complaint, "complaints.transfer")
    check_permission(actor, "complaints.transfer", data.directorate_id)
    directorate_or_422(db, data.directorate_id)
    if complaint.directorate_id == data.directorate_id:
        raise HTTPException(409, "الشكوى موجودة في المديرية المطلوبة")
    db.info["history_reason"] = data.reason
    complaint.directorate_id = data.directorate_id
    db.commit()
    return {"id": identifier, "directorate_id": complaint.directorate_id}
