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


def employee_data(employee):
    return {
        "id": employee.id, "username": employee.username,
        "full_name": employee.full_name, "role": employee.role.value,
        "directorate_id": employee.directorate_id,
    }


def provision_accounts(db: Session):
    """Create missing accounts only; never overwrite existing passwords at startup."""
    for username, secret_key, role, directorate_id, name in [
        ("governor", "GOVERNOR_PASSWORD", UserRole.GOVERNOR, None, "حساب المحافظة"),
        ("services", "SERVICES_PASSWORD", UserRole.EMPLOYEE, 2, "حساب الخدمات"),
    ]:
        if db.query(Employee).filter_by(username=username).first():
            continue
        password = os.environ.get(secret_key)
        if not password:
            continue
        if len(password) < 12:
            raise RuntimeError(f"{secret_key} must have at least 12 characters")
        next_id = (db.query(func.max(Employee.id)).scalar() or 0) + 1
        db.add(Employee(id=next_id, username=username, full_name=name,
                        hashed_password=hash_password(password), role=role,
                        directorate_id=directorate_id))
        db.commit()


@router.get("/config")
def auth_config(db: Session = Depends(get_db)):
    return {"configured": db.query(Employee).count() > 0}


@router.post("/login")
def login(data: LoginInput, request: Request, db: Session = Depends(get_db)):
    check_login_rate(request)
    employee = db.query(Employee).filter_by(username=data.username.strip()).first()
    # Run a hash even when the username is unknown, avoiding a fast existence check.
    valid = verify_password(data.password, employee.hashed_password) if employee else (
        verify_password(data.password, hash_password("non-account-placeholder"))
    )
    if not employee or not valid:
        raise HTTPException(401, "اسم المستخدم أو كلمة المرور غير صحيحة")
    request.session.clear()
    request.session["employee_id"] = employee.id
    return employee_data(employee)


@router.get("/me")
def me(employee=Depends(current_employee)):
    return employee_data(employee)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}
