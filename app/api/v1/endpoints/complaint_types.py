from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.complaint import ComplaintType
from app.schemas.complaint_type import ComplaintTypeCreate, ComplaintTypeUpdate
from app.services.access import require_permission
from app.services.access_admin import begin_change, finish_change
from app.services.complaint_types import complaint_type_data

router = APIRouter()
manage = require_permission("complaint_types.manage", global_only=True)


@router.get("/complaint-types")
def public_types(lang: str | None = Query(default=None, max_length=35), db: Session = Depends(get_db)):
    rows = db.query(ComplaintType).filter_by(is_active=True).order_by(ComplaintType.id).all()
    return [complaint_type_data(row, lang) for row in rows]


@router.get("/admin/complaint-types")
def admin_types(
    lang: str | None = Query(default=None, max_length=35),
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    rows = db.query(ComplaintType).order_by(ComplaintType.id).all()
    return [complaint_type_data(row, lang) for row in rows]


@router.post("/admin/complaint-types", status_code=201)
def create_type(data: ComplaintTypeCreate, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor, "complaint_types.manage")
    row = ComplaintType(
        code=f"custom-{uuid4().hex}",
        name=data.name,
        description=data.description,
        sla_duration_minutes=data.sla_duration_minutes,
        is_active=True,
    )
    db.add(row)
    db.flush()
    finish_change(db, actor, "complaint_type.create", "complaint_type", row.id)
    return complaint_type_data(row)


@router.put("/admin/complaint-types/{identifier}")
def update_type(
    identifier: int,
    data: ComplaintTypeUpdate,
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    begin_change(db, actor, "complaint_types.manage")
    row = db.get(ComplaintType, identifier)
    if not row:
        raise HTTPException(404, "نوع الشكوى غير موجود")
    if row.code == "other":
        if data.sla_duration_minutes is not None:
            raise HTTPException(422, "نوع «أخرى» لا يقبل مهلة زمنية")
        if not data.is_active:
            raise HTTPException(409, "لا يمكن تعطيل نوع «أخرى»")
    elif data.is_active and data.sla_duration_minutes is None:
        raise HTTPException(422, "حدد المهلة قبل إبقاء النوع مفعّلًا")
    row.name = data.name
    row.description = data.description
    row.sla_duration_minutes = data.sla_duration_minutes
    row.is_active = data.is_active
    finish_change(db, actor, "complaint_type.update", "complaint_type", row.id)
    return complaint_type_data(row)
