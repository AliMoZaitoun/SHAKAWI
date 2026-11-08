import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import check_login_rate, current_employee, hash_password, verify_password
from app.db.session import get_db
from app.models.user import Employee, UserRole

router = APIRouter()


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


def is_production():
    return os.environ.get("REPLIT_DEPLOYMENT") == "1" or os.environ.get("APP_ENV") == "production"


def demo_enabled():
    return os.environ.get("ENABLE_DEMO_ACCOUNTS") == "1" and not is_production()


def employee_data(employee):
    from app.services.access import permission_scopes, PERMISSIONS
    from app.services.translations import localized
    return {
        "id": employee.id, "username": employee.username,
        "full_name": employee.full_name, "role": employee.role.value,
        "directorate_id": employee.directorate_id,
        "is_demo": employee.is_demo, "password_version": employee.password_version,
        "user_id": employee.user_id,
        "roles": [{"id": row.role.id, "code": row.role.code, "name": localized(row.role)["name"],
                   "scope_type": row.scope_type, "directorate_id": row.directorate_id}
                  for row in employee.role_assignments],
        "permissions": {
            code: {"scope_type": "global" if scopes is None else "directorate",
                   "directorate_ids": None if scopes is None else sorted(scopes)}
            for code in PERMISSIONS
            if (scopes := permission_scopes(employee, code)) is None or scopes
        },
    }


def provision_accounts(db: Session):
    """Create missing accounts only; never overwrite existing passwords at startup."""
    if is_production():
        if os.environ.get("ENABLE_DEMO_ACCOUNTS") == "1":
            raise RuntimeError("Demo accounts must be disabled before production")
        if any(employee.is_demo or verify_password("123456", employee.hashed_password)
               for employee in db.query(Employee).all()):
            raise RuntimeError("Change all temporary demo passwords before production")
    for username, secret_key, role, directorate_id, name in [
        ("governor", "GOVERNOR_PASSWORD", UserRole.GOVERNOR, None, "حساب المحافظة"),
        ("services", "SERVICES_PASSWORD", UserRole.EMPLOYEE, 2, "حساب الخدمات"),
    ]:
        if db.query(Employee).filter_by(username=username).first():
            continue
        password = os.environ.get(secret_key)
        is_demo = False
        if not password and demo_enabled():
            password = "123456"
            is_demo = True
        if not password:
            continue
        if not is_demo and len(password) < 12:
            raise RuntimeError(f"{secret_key} must have at least 12 characters")
        next_id = (db.query(func.max(Employee.id)).scalar() or 0) + 1
        db.add(Employee(id=next_id, username=username, full_name=name,
                        hashed_password=hash_password(password), role=role,
                         is_demo=is_demo,
                        directorate_id=directorate_id))
        db.commit()


@router.get("/config")
def auth_config(db: Session = Depends(get_db)):
    return {"configured": db.query(Employee).count() > 0,
            "demo_mode": db.query(Employee).filter_by(is_demo=True).count() > 0}


@router.post("/login")
def login(data: LoginInput, request: Request, db: Session = Depends(get_db)):
    check_login_rate(request)
    employee = db.query(Employee).filter_by(username=data.username.strip()).first()
    # Run a hash even when the username is unknown, avoiding a fast existence check.
    valid = verify_password(data.password, employee.hashed_password) if employee else (
        verify_password(data.password, hash_password("non-account-placeholder"))
    )
    if not employee or not valid or not employee.user or not employee.user.is_active:
        raise HTTPException(401, "اسم المستخدم أو كلمة المرور غير صحيحة")
    from app.services.audit import record_event
    record_event(db, "auth.login", "users", employee.user_id, actor_user_id=employee.user_id)
    db.commit()
    request.session.clear()
    request.session["employee_id"] = employee.id
    request.session["password_version"] = employee.password_version
    return employee_data(employee)


@router.get("/me")
def me(employee=Depends(current_employee)):
    return employee_data(employee)


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    from app.services.audit import record_event
    from app.services.request_context import request_context
    actor = request_context.get().get("actor_user_id")
    if actor:
        record_event(db, "auth.logout", "users", actor)
        db.commit()
    request.session.clear()
    return {"ok": True}


@router.post("/change-password")
def change_password(data: PasswordChange, request: Request,
                    employee=Depends(current_employee), db: Session = Depends(get_db)):
    check_login_rate(request)
    if not verify_password(data.current_password, employee.hashed_password):
        raise HTTPException(400, "كلمة المرور الحالية غير صحيحة")
    if data.current_password == data.new_password:
        raise HTTPException(422, "اختر كلمة مرور مختلفة")
    employee.hashed_password = hash_password(data.new_password)
    employee.is_demo = False
    employee.password_version += 1
    db.commit()
    request.session["password_version"] = employee.password_version
    return employee_data(employee)
