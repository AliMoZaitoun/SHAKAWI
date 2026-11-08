from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.access import Directorate, Role, RoleAssignment
from app.models.complaint import Complaint
from app.models.user import Employee
from app.schemas.access import DirectorateInput
from app.services.access import require_permission
from app.services.access_admin import begin_change, finish_change

router = APIRouter()
manage = require_permission("directorates.manage", global_only=True)


def serialize(row, db=None):
    from app.services.translations import localized
    data = {"id": row.id, **localized(row), "is_active": row.is_active}
    if db is not None:
        assignment = db.query(RoleAssignment).join(Role).filter(
            Role.code == "branch_manager", RoleAssignment.directorate_id == row.id,
            RoleAssignment.scope_type == "directorate",
        ).first()
        manager = assignment.employee if assignment else None
        data["current_manager"] = (
            {"employee_id": manager.id, "full_name": manager.full_name}
            if manager and manager.user and manager.user.is_active else None
        )
    return data


@router.get("/directorates")
def public_directory(db: Session = Depends(get_db)):
    # No employee details in the citizen-facing dropdown/catalog.
    return [serialize(row) for row in db.query(Directorate).filter_by(is_active=True).order_by(Directorate.id)]


@router.get("/admin/directorates")
def directory(actor=Depends(manage), db: Session = Depends(get_db)):
    return [serialize(row, db) for row in db.query(Directorate).order_by(Directorate.id)]


@router.post("/admin/directorates", status_code=201)
def create(data: DirectorateInput, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor, "directorates.manage")
    row = Directorate(**data.model_dump())
    db.add(row)
    db.flush()
    finish_change(db, actor, "directorate.create", "directorate", row.id)
    return serialize(row, db)


@router.put("/admin/directorates/{identifier}")
def edit(identifier: int, data: DirectorateInput, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor, "directorates.manage")
    row = db.get(Directorate, identifier)
    if not row:
        raise HTTPException(404, "المديرية غير موجودة")
    for key, value in data.model_dump().items():
        setattr(row, key, value)
    finish_change(db, actor, "directorate.update", "directorate", identifier)
    return serialize(row, db)


@router.delete("/admin/directorates/{identifier}")
def delete(identifier: int, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor, "directorates.manage")
    row = db.get(Directorate, identifier)
    if not row:
        raise HTTPException(404, "المديرية غير موجودة")
    if (db.query(Complaint).filter_by(directorate_id=identifier).first()
            or db.query(Employee).filter_by(directorate_id=identifier).first()
            or db.query(RoleAssignment).filter_by(directorate_id=identifier).first()):
        raise HTTPException(409, "المديرية مستخدمة؛ عطّلها بدل حذف علاقاتها")
    db.delete(row)
    finish_change(db, actor, "directorate.delete", "directorate", identifier)
    return {"ok": True}
