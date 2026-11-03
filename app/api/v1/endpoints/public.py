from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.complaint import Complaint, StatusEnum
from app.services.public_complaints import public_complaint

router = APIRouter()


@router.get("")
@router.get("/")
def public_list(page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=50),
                category: str | None = Query(None, max_length=50),
                status: StatusEnum | None = None,
                directorate_id: int | None = Query(None, ge=1, le=2),
                db: Session = Depends(get_db)):
    query = db.query(Complaint).filter(Complaint.is_public.is_(True))
    if category:
        query = query.filter(Complaint.category == category)
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
