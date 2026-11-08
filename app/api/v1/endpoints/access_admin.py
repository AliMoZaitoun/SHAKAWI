"""Administration API for a future React client; no frontend replacement."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.models.access import AccessAudit, Permission, Role, RoleAssignment, User
from app.models.user import Employee, UserRole
from app.schemas.access import (
    AssignmentInput, EmployeeInput, EmployeeUpdate, PermissionUpdate, RoleInput, RoleUpdate,
)
from app.services.access import require_permission
from app.services.access_admin import (
    assignment_data, begin_change, directorate_or_422, employee_data, finish_change,
    permission_rows, role_data,
)

router = APIRouter()
manage = require_permission("rbac.manage", global_only=True)
manage_employees = require_permission("employees.manage", global_only=True)


def find(db, model, identifier):
    row = db.get(model, identifier)
    if row is None:
        raise HTTPException(404, "السجل غير موجود")
    return row


@router.get("/permissions")
def permissions(actor=Depends(manage), db: Session = Depends(get_db)):
    return [{"code": row.code, "name": row.name, "description": row.description}
            for row in db.query(Permission).order_by(Permission.code)]


@router.patch("/permissions/{code}")
def edit_permission(code: str, data: PermissionUpdate, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    row = find(db, Permission, code)
    row.name, row.description = data.name, data.description
    finish_change(db, actor, "permission.update", "permission", code)
    return {"code": row.code, "name": row.name, "description": row.description}


@router.get("/roles")
def roles(actor=Depends(manage), db: Session = Depends(get_db)):
    return [role_data(row) for row in db.query(Role).order_by(Role.id)]


@router.post("/roles", status_code=201)
def create_role(data: RoleInput, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    if db.query(Role).filter_by(code=data.code).first():
        raise HTTPException(409, "رمز الدور مستخدم")
    row = Role(code=data.code, name=data.name, description=data.description,
               permissions=permission_rows(db, data.permissions))
    db.add(row)
    db.flush()
    finish_change(db, actor, "role.create", "role", row.id, {"permissions": sorted(set(data.permissions))})
    return role_data(row)


@router.put("/roles/{role_id}")
def edit_role(role_id: int, data: RoleUpdate, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    row = find(db, Role, role_id)
    row.name, row.description = data.name, data.description
    row.permissions = permission_rows(db, data.permissions)
    finish_change(db, actor, "role.update", "role", row.id, {"permissions": sorted(set(data.permissions))})
    return role_data(row)


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    row = find(db, Role, role_id)
    if row.is_system or db.query(RoleAssignment).filter_by(role_id=role_id).first():
        raise HTTPException(409, "لا يمكن حذف دور نظامي أو دور مسند لموظف")
    db.delete(row)
    finish_change(db, actor, "role.delete", "role", role_id)
    return {"ok": True}


@router.get("/employees")
def employees(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
              actor=Depends(manage_employees), db: Session = Depends(get_db)):
    query = db.query(Employee).order_by(Employee.id)
    return {"total": query.count(), "page": page,
            "items": [employee_data(row) for row in query.offset((page - 1) * page_size).limit(page_size)]}


@router.post("/employees", status_code=201)
def create_employee(data: EmployeeInput, actor=Depends(manage_employees), db: Session = Depends(get_db)):
    begin_change(db, actor, "employees.manage")
    directorate_or_422(db, data.directorate_id)
    if (db.query(User).filter((User.username == data.username) | (User.phone == data.phone)
                             | ((User.email == data.email) if data.email else False)).first()):
        raise HTTPException(409, "اسم المستخدم أو وسيلة الاتصال مستخدمة؛ لا يتم دمج السجلات تلقائيًا")
    user = User(first_name=data.first_name, last_name=data.last_name, phone=data.phone,
                email=data.email, username=data.username, hashed_password=hash_password(data.password),
                user_type="employee", needs_profile_completion=False)
    row = Employee(id=(db.query(func.max(Employee.id)).scalar() or 0) + 1,
                   user=user, full_name=f"{data.first_name} {data.last_name}", username=data.username,
                   hashed_password=user.hashed_password, role=UserRole.EMPLOYEE,
                   directorate_id=data.directorate_id, rbac_initialized=True)
    db.add(row)
    db.flush()
    finish_change(db, actor, "employee.create", "employee", row.id)
    return employee_data(row)


@router.put("/employees/{employee_id}")
def edit_employee(employee_id: int, data: EmployeeUpdate,
                  actor=Depends(manage_employees), db: Session = Depends(get_db)):
    begin_change(db, actor, "employees.manage")
    row = find(db, Employee, employee_id)
    directorate_or_422(db, data.directorate_id)
    for field in ("first_name", "last_name", "phone", "email", "is_active"):
        setattr(row.user, field, getattr(data, field))
    row.user.needs_profile_completion = False
    row.directorate_id = data.directorate_id
    # Disable/reactivate never resurrects a previously issued session.
    row.password_version += 1
    finish_change(db, actor, "employee.update", "employee", employee_id,
                  {"fields": ["profile", "directorate_id", "is_active"]})
    return employee_data(row)


@router.post("/employees/{employee_id}/roles", status_code=201)
def assign_role(employee_id: int, data: AssignmentInput,
                actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    employee = find(db, Employee, employee_id)
    role = find(db, Role, data.role_id)
    if (data.scope_type == "global") != (data.directorate_id is None):
        raise HTTPException(422, "النطاق العام لا يقبل مديرية، ونطاق المديرية يتطلب رقمها")
    directorate_or_422(db, data.directorate_id)
    scope_key = data.directorate_id or 0
    if db.query(RoleAssignment).filter_by(employee_id=employee_id, role_id=role.id, scope_key=scope_key).first():
        raise HTTPException(409, "الدور مسند مسبقًا ضمن نفس النطاق")
    if role.code == "branch_manager":
        if data.scope_type != "directorate":
            raise HTTPException(422, "مدير الفرع يحتاج فرعًا محددًا")
        if db.query(RoleAssignment).filter_by(role_id=role.id, directorate_id=data.directorate_id).first():
            raise HTTPException(409, "يوجد مدير حالي للفرع؛ ألغِ التكليف السابق أولًا")
    row = RoleAssignment(employee=employee, role=role, scope_type=data.scope_type,
                         directorate_id=data.directorate_id, scope_key=scope_key)
    db.add(row)
    db.flush()
    finish_change(db, actor, "role.assign", "assignment", row.id,
                  {"employee_id": employee_id, "role_id": role.id, "scope_key": scope_key})
    return assignment_data(row)


@router.delete("/employees/{employee_id}/roles/{assignment_id}")
def revoke_role(employee_id: int, assignment_id: int,
                actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    row = find(db, RoleAssignment, assignment_id)
    if row.employee_id != employee_id:
        raise HTTPException(404, "التكليف غير موجود لهذا الموظف")
    db.delete(row)
    finish_change(db, actor, "role.revoke", "assignment", assignment_id, {"employee_id": employee_id})
    return {"ok": True}


@router.get("/audit")
def audit(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
          actor=Depends(manage), db: Session = Depends(get_db)):
    query = db.query(AccessAudit).order_by(AccessAudit.id.desc())
    return {"total": query.count(), "page": page, "items": [
        {"id": row.id, "actor_id": row.actor_id, "action": row.action,
         "target_type": row.target_type, "target_id": row.target_id,
         "details": row.details, "created_at": row.created_at}
        for row in query.offset((page - 1) * page_size).limit(page_size)]}
