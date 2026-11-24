from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.complaint import Complaint, ComplaintType, StatusEnum, PublicComplaintReport
from app.core.security import _attempts
import time
from app.services.public_complaints import public_complaint
from app.services.translations import localized
from app.schemas.public_review import ReportInput

router = APIRouter()


@router.post("/{complaint_id}/reports", status_code=201)
def report_public_text(complaint_id: int, data: ReportInput, request: Request,
                       db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id, Complaint.is_public.is_(True)
    ).first()
    if not complaint:
        raise HTTPException(404, "الشكوى العامة غير موجودة")
    # Reporting never hides a complaint automatically. Limit unauthenticated
    # writes using the socket peer, not caller-controlled forwarded headers.
    key = ("public-report", request.client.host if request.client else "unknown")
    attempts = _attempts[key]
    now = time.monotonic()
    while attempts and now - attempts[0] > 600:
        attempts.popleft()
    if len(attempts) >= 10:
        raise HTTPException(429, "بلاغات كثيرة، حاول بعد عشر دقائق")
    attempts.append(now)
    db.add(PublicComplaintReport(complaint_id=complaint_id, reason=data.reason))
    db.commit()
    return {"message": "تم استلام البلاغ للمراجعة. لا يؤدي البلاغ وحده إلى إخفاء النصوص."}


@router.get("")
@router.get("/")
def public_list(page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=50),
                category: str | None = Query(None, max_length=150),
                complaint_type_id: int | None = Query(None, ge=1),
                status: StatusEnum | None = None,
                directorate_id: int | None = Query(None, ge=1),
                db: Session = Depends(get_db)):
    from app.services.access_admin import directorate_or_422
    directorate_or_422(db, directorate_id, active=False)
    query = db.query(Complaint).filter(Complaint.is_public.is_(True))
    if complaint_type_id is not None:
        query = query.filter(Complaint.complaint_type_id == complaint_type_id)
    if category:
        matching_type_ids = [
            row.id for row in db.query(ComplaintType)
            if localized(row)["name"] == category
        ]
        category_filter = Complaint.category == category
        if matching_type_ids:
            category_filter = or_(category_filter, Complaint.complaint_type_id.in_(matching_type_ids))
        query = query.filter(category_filter)
    if status:
        query = query.filter(Complaint.status == status)
    if directorate_id is not None:
        query = query.filter(Complaint.directorate_id == directorate_id)
    total = query.count()
    rows = query.options(selectinload(Complaint.notes), selectinload(Complaint.citizen)).order_by(
        Complaint.created_at.desc(), Complaint.id.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [public_complaint(row) for row in rows],
        "total": total, "page": page, "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/{complaint_id}")
def public_detail(complaint_id: int, db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id, Complaint.is_public.is_(True)
    ).first()
    if not complaint:
        raise HTTPException(404, "الشكوى العامة غير موجودة")
    return public_complaint(complaint)
