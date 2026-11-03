from pathlib import Path

from fastapi import APIRouter, Body, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from app.core.security import authorize_complaint, current_employee, is_bot, owns_citizen, require_bot
from app.db.session import get_db
from app.models.complaint import Attachment, Complaint, ComplaintNote, StatusEnum
from app.models.user import Citizen, UserRole
from app.schemas.complaint import ComplaintCreate, NoteCreate, ProcessingUpdate
from app.services.complaint_service import ComplaintService
from app.services.notifications import MESSAGES, notify, notify_note
from app.services.uploads import UPLOAD_DIR, save_upload

router = APIRouter()


def find_complaint(db, complaint_id):
    complaint = db.get(Complaint, complaint_id)
    if not complaint:
        raise HTTPException(404, "الشكوى غير موجودة")
    return complaint


def note_data(note, staff=False):
    data = {
        "id": note.id, "note": note.note, "is_internal": note.is_internal,
        "created_at": note.created_at,
    }
    if staff:
        data.update(author_name=note.author.full_name if note.author else "موظف",
                    notification_status=note.notification_status,
                    notification_error=note.notification_error)
    return data


def complaint_data(db, complaint, staff=False):
    notes = sorted(complaint.notes, key=lambda n: n.id)
    visible = notes if staff else [n for n in notes if not n.is_internal]
    public_notes = [n for n in notes if not n.is_internal]
    data = {
        "id": complaint.id, "tracking_code": complaint.tracking_code,
        "directorate_id": complaint.directorate_id, "title": complaint.title,
        "details": complaint.details, "category": complaint.category,
        "is_public": complaint.is_public,
        "priority": complaint.priority, "status": complaint.status,
        "created_at": complaint.created_at, "updated_at": complaint.updated_at,
        "progress": complaint.progress, "resolution_report": complaint.resolution_report,
        "notes": [note_data(n, staff) for n in visible],
        "admin_notes": public_notes[-1].note if public_notes else "",
        "attachments": [],
    }
    if staff:
        citizen = complaint.citizen
        data["citizen"] = {
            "first_name": citizen.first_name, "last_name": citizen.last_name,
            "phone": citizen.phone, "national_id": citizen.national_id,
        } if citizen else None
        for item in db.query(Attachment).filter(
            Attachment.attachable_id == complaint.id,
            Attachment.attachable_type.in_(["complaint", "complaints"]),
        ).all():
            data["attachments"].append({
                "id": item.id, "file_path": item.file_path, "file_type": item.file_type,
                "file_url": f"/api/v1/complaints/attachments/{item.id}/download",
            })
    return data


@router.post("/")
def create_complaint(data: ComplaintCreate, request: Request, db: Session = Depends(get_db)):
    if not is_bot(request) and not owns_citizen(request, data.citizen_id):
        raise HTTPException(403, "يرجى إدخال بيانات المواطن أولاً")
    if not db.get(Citizen, data.citizen_id):
        raise HTTPException(404, "المواطن غير موجود")
    complaint = ComplaintService.create_complaint(db, data)
    return complaint_data(db, complaint)


@router.get("/")
def list_complaints(employee=Depends(current_employee), db: Session = Depends(get_db)):
    query = db.query(Complaint).options(selectinload(Complaint.notes), selectinload(Complaint.citizen))
    if employee.role != UserRole.GOVERNOR:
        query = query.filter(Complaint.directorate_id == employee.directorate_id)
    return [complaint_data(db, c, staff=True) for c in query.order_by(Complaint.id.desc()).all()]


@router.get("/track/{tracking_code}")
def track(tracking_code: str, db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter_by(tracking_code=tracking_code.strip().upper()).first()
    if not complaint:
        raise HTTPException(404, "رمز التتبع غير موجود")
    return complaint_data(db, complaint)


@router.get("/citizen/{citizen_id}", dependencies=[Depends(require_bot)])
def by_citizen(citizen_id: int, db: Session = Depends(get_db)):
    return [complaint_data(db, c) for c in db.query(Complaint).filter_by(citizen_id=citizen_id).all()]


@router.get("/attachments/{attachment_id}/download")
def download(attachment_id: int, employee=Depends(current_employee), db: Session = Depends(get_db)):
    item = db.get(Attachment, attachment_id)
    if not item or item.attachable_type not in ("complaint", "complaints"):
        raise HTTPException(404, "المرفق غير موجود")
    complaint = find_complaint(db, item.attachable_id)
    authorize_complaint(employee, complaint)
    path = Path(item.file_path).resolve()
    if not path.is_relative_to(UPLOAD_DIR.resolve()) or not path.is_file():
        raise HTTPException(404, "ملف المرفق غير موجود")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@router.get("/{complaint_id}")
def get_complaint(complaint_id: int, request: Request, db: Session = Depends(get_db)):
    complaint = find_complaint(db, complaint_id)
    if is_bot(request):
        return complaint_data(db, complaint)
    employee = current_employee(request, db)
    authorize_complaint(employee, complaint)
    return complaint_data(db, complaint, staff=True)


@router.post("/{complaint_id}/attachments/")
async def upload_attachment(complaint_id: int, request: Request, file: UploadFile = File(...),
                            db: Session = Depends(get_db)):
    complaint = find_complaint(db, complaint_id)
    if not is_bot(request) and not owns_citizen(request, complaint.citizen_id):
        employee = current_employee(request, db)
        authorize_complaint(employee, complaint)
    path = await save_upload(file)
    item = Attachment(file_path=path, file_type=file.content_type or "unknown",
                      attachable_type="complaint", attachable_id=complaint_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "file_path": path, "message": "تم حفظ المرفق"}


@router.patch("/{complaint_id}/status")
async def update_status(complaint_id: int, new_status: StatusEnum,
                        data: ProcessingUpdate = Body(default_factory=ProcessingUpdate),
                        employee=Depends(current_employee), db: Session = Depends(get_db)):
    complaint = find_complaint(db, complaint_id)
    authorize_complaint(employee, complaint)
    old_status = complaint.status
    if new_status != StatusEnum.RESOLVED and data.progress == 100:
        raise HTTPException(422, "نسبة 100٪ مخصصة للشكاوى المحلولة فقط")
    complaint.status = new_status
    if data.progress is not None:
        complaint.progress = data.progress
    if new_status == StatusEnum.RESOLVED:
        complaint.progress = 100
    elif complaint.progress == 100:
        complaint.progress = 0
    if data.resolution_report is not None:
        complaint.resolution_report = data.resolution_report
    if data.priority is not None:
        complaint.priority = data.priority
    note = None
    if data.admin_notes.strip():
        note = ComplaintNote(complaint_id=complaint.id, author_id=employee.id,
                             note=data.admin_notes.strip(), is_internal=False)
        db.add(note)
    # Commit the complaint and note together before any external network request.
    db.commit()
    notification = {"status": "not_requested", "message": MESSAGES["not_requested"]}
    if note:
        notification = await notify_note(db, complaint, note)
    elif old_status != new_status:
        labels = {"PENDING": "قيد الانتظار", "IN_PROGRESS": "قيد المعالجة",
                  "RESOLVED": "تمت المعالجة", "REJECTED": "مرفوضة"}
        notification = await notify(complaint.citizen, complaint.tracking_code,
                                    "حالة الشكوى: " + labels[new_status.value])
    return {"message": "تم حفظ تحديث الشكوى", "new_status": new_status,
            "notification": notification}


@router.post("/{complaint_id}/notes")
async def add_note(complaint_id: int, data: NoteCreate,
                   employee=Depends(current_employee), db: Session = Depends(get_db)):
    complaint = find_complaint(db, complaint_id)
    authorize_complaint(employee, complaint)
    if not data.note.strip():
        raise HTTPException(422, "الملاحظة لا يمكن أن تكون فارغة")
    note = ComplaintNote(complaint_id=complaint_id, author_id=employee.id,
                         note=data.note.strip(), is_internal=data.is_internal)
    db.add(note)
    db.commit()
    notification = await notify_note(db, complaint, note)
    return {"note": note_data(note, staff=True), "notification": notification}


@router.post("/{complaint_id}/notes/{note_id}/retry")
async def retry_note(complaint_id: int, note_id: int,
                     employee=Depends(current_employee), db: Session = Depends(get_db)):
    complaint = find_complaint(db, complaint_id)
    authorize_complaint(employee, complaint)
    note = db.get(ComplaintNote, note_id)
    if not note or note.complaint_id != complaint_id or note.is_internal:
        raise HTTPException(404, "الملاحظة غير موجودة")
    if note.notification_status == "sent":
        return {"status": "sent", "message": MESSAGES["sent"]}
    return await notify_note(db, complaint, note)
