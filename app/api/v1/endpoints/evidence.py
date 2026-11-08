"""Complaint-scoped staff requests and atomic citizen answers."""
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (authorize_complaint, authorize_owner, authorize_reader,
                               current_employee, is_bot)
from app.db.session import get_db
from app.models.complaint import Complaint, EvidenceRequest, EvidenceReply, EvidenceFile
from app.services.evidence import request_data, reply_data, validate_files, payload_digest, store_file
from app.services.notifications import notify, MESSAGES
from app.services.uploads import UPLOAD_DIR

router = APIRouter()


class RequestInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    submission_key: str = Field(min_length=16, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


def find(db, cid, rid=None):
    complaint = db.get(Complaint, cid)
    if not complaint:
        raise HTTPException(404, "الشكوى غير موجودة")
    if rid is None:
        return complaint
    row = db.get(EvidenceRequest, rid)
    if not row or row.complaint_id != cid:
        raise HTTPException(404, "طلب الاستكمال غير موجود")
    return complaint, row


async def send_request(db, complaint, row):
    now = int(time.time())
    # Atomic claim survives concurrent retries; a crashed sender is retryable after 30s.
    changed = db.query(EvidenceRequest).filter(
        EvidenceRequest.id == row.id, EvidenceRequest.notification_status != "sent",
        EvidenceRequest.notification_attempted_at <= now - 30,
    ).update({"notification_attempted_at": now}, synchronize_session=False)
    db.commit()
    db.refresh(row)
    if not changed:
        if row.notification_status == "sent":
            return {"status": "sent", "message": MESSAGES["sent"]}
        raise HTTPException(429, "انتظر 30 ثانية قبل إعادة محاولة الإشعار")
    result = await notify(
        complaint.citizen, complaint.tracking_code,
        "طلب استكمال معلومات أو أدلة:\n" + row.prompt,
        reply_markup={"inline_keyboard": [[{"text": "إرسال الأدلة",
                                           "callback_data": f"evidence_{complaint.id}_{row.id}"}]]},
    )
    row.notification_status = result["status"]
    row.notification_error = None if result["status"] == "sent" else result["message"]
    db.commit()
    return result


@router.post("/complaints/{cid}/evidence")
async def create(cid: int, data: RequestInput, employee=Depends(current_employee),
                 db: Session = Depends(get_db)):
    complaint = find(db, cid)
    authorize_complaint(employee, complaint, "evidence.request")
    if not data.prompt.strip():
        raise HTTPException(422, "اكتب المعلومات المطلوبة")
    old = db.query(EvidenceRequest).filter_by(complaint_id=cid, submission_key=data.submission_key).first()
    if old:
        if old.prompt != data.prompt.strip():
            raise HTTPException(409, "لا يمكن تغيير مضمون طلب محفوظ بالمفتاح نفسه")
        return {"request": request_data(old, True),
                "notification": {"status": old.notification_status,
                                 "message": MESSAGES.get(old.notification_status, MESSAGES["failed"])}}
    row = EvidenceRequest(complaint_id=cid, author_id=employee.id, prompt=data.prompt.strip(),
                          submission_key=data.submission_key)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return await create(cid, data, employee, db)
    result = await send_request(db, complaint, row)
    return {"request": request_data(row, True), "notification": result}


@router.get("/complaints/{cid}/evidence")
def listing(cid: int, request: Request, db: Session = Depends(get_db)):
    complaint = find(db, cid)
    authorize_reader(request, db, complaint)
    staff = bool(request.session.get("employee_id")) and not is_bot(request)
    if staff:
        authorize_complaint(current_employee(request, db), complaint, "evidence.read")
    return [request_data(r, staff) for r in complaint.evidence_requests]


@router.post("/complaints/{cid}/evidence/{rid}/retry")
async def retry(cid: int, rid: int, employee=Depends(current_employee), db: Session = Depends(get_db)):
    complaint, row = find(db, cid, rid)
    authorize_complaint(employee, complaint, "notifications.retry")
    authorize_complaint(employee, complaint, "evidence.read")
    if row.status != "pending":
        raise HTTPException(409, "أجاب المواطن؛ لا حاجة لتنبيه جديد")
    return await send_request(db, complaint, row)


@router.post("/complaints/{cid}/evidence/{rid}/reply")
async def answer(cid: int, rid: int, request: Request, text: str = Form(""),
                 submission_key: str = Form(..., min_length=16, max_length=80,
                                            pattern=r"^[A-Za-z0-9_-]+$"),
                 files: list[UploadFile] = File(default=[]), db: Session = Depends(get_db)):
    complaint, row = find(db, cid, rid)
    authorize_owner(request, db, complaint)
    text = text.strip()
    if len(text) > 10000 or (not text and not files):
        raise HTTPException(422, "أضف نصًا لا يتجاوز 10000 حرف أو مرفقًا")
    validated = await validate_files(files)
    digest = payload_digest(text, validated)

    def existing():
        old = db.query(EvidenceReply).filter_by(request_id=rid).first()
        if old and old.submission_key == submission_key and old.payload_digest == digest:
            return {"reply": reply_data(old)}
        raise HTTPException(409, "تم الرد على هذا الطلب بالفعل؛ لم يُحفظ رد آخر")

    if row.replies:
        return existing()
    paths = []
    try:
        reply = EvidenceReply(request_id=rid, text=text, submission_key=submission_key,
                              payload_digest=digest, channel="telegram" if is_bot(request) else "web")
        db.add(reply)
        db.flush()
        for name, mime, suffix, raw in validated:
            path = store_file(suffix, raw)
            paths.append(path)
            db.add(EvidenceFile(reply_id=reply.id, name=name, file_path=path, file_type=mime))
        row.status = "answered"
        db.commit()
    except Exception as exc:
        db.rollback()
        for path in paths:
            Path(path).unlink(missing_ok=True)
        if isinstance(exc, IntegrityError):
            return existing()
        raise
    return {"reply": reply_data(reply)}


@router.get("/evidence-files/{fid}/download")
def download(fid: int, request: Request, db: Session = Depends(get_db)):
    item = db.get(EvidenceFile, fid)
    if not item:
        raise HTTPException(404, "المرفق غير موجود")
    reply = db.get(EvidenceReply, item.reply_id)
    row = db.get(EvidenceRequest, reply.request_id)
    authorize_reader(request, db, find(db, row.complaint_id))
    if request.session.get("employee_id") and not is_bot(request):
        authorize_complaint(current_employee(request, db), find(db, row.complaint_id), "evidence.files.read")
    path = Path(item.file_path).resolve()
    if not path.is_relative_to((UPLOAD_DIR / "evidence").resolve()) or not path.is_file():
        raise HTTPException(404, "الملف غير موجود")
    return FileResponse(path, filename=item.name, media_type="application/octet-stream",
                        headers={"X-Content-Type-Options": "nosniff"})
