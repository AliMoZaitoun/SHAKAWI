"""Password hashing and authorization for the imported employee accounts."""
import base64
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from jwt import InvalidTokenError
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import Citizen, Employee
from app.core.tokens import decode_access_token

_attempts = defaultdict(deque)


def credential_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def grant_citizen(request: Request, citizen_id: int):
    request.session["citizen_id"] = citizen_id
    request.session["citizen_ownership"] = "registration-v2"


def check_recovery_rate(request: Request):
    # Separate from staff login. Read the socket peer, never a caller-supplied
    # forwarded address. Credentials also have 256 bits of entropy.
    key = ("recovery", request.client.host if request.client else "unknown")
    now = time.monotonic()
    attempts = _attempts[key]
    while attempts and now - attempts[0] > 600:
        attempts.popleft()
    if len(attempts) >= 20:
        raise HTTPException(429, "محاولات كثيرة، حاول بعد عشر دقائق")
    attempts.append(now)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt, expected = encoded.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(digest, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False


def is_bot(request: Request) -> bool:
    token = os.environ.get("BOT_TOKEN", "")
    return bool(token) and hmac.compare_digest(request.headers.get("X-Bot-Token", ""), token)


def require_bot(request: Request):
    if not is_bot(request):
        raise HTTPException(401, "هذا المسار مخصص للبوت")


def require_bot_owner(request: Request, db: Session, citizen_id: int):
    require_bot(request)
    try:
        telegram_id = int(request.headers.get("X-Telegram-Id", ""))
    except ValueError:
        raise HTTPException(403, "يلزم تحديد حساب تيليغرام الحالي")
    citizen = db.query(Citizen).filter_by(id=citizen_id, telegram_id=telegram_id).first()
    if not citizen:
        raise HTTPException(403, "لم يعد حساب تيليغرام مرتبطًا بهذا السجل")
    from app.services.request_context import request_context
    # Mutate this request's metadata so sync dependencies and async handlers
    # share the authenticated actor without trusting caller-supplied user IDs.
    request_context.get()["actor_user_id"] = citizen.user_id


def owns_citizen(request: Request, citizen_id: int) -> bool:
    # Only newly registered browser sessions get this capability. A replay of
    # someone else's personal details must never issue it. Versioning also
    # rejects old cookies issued by the previously permissive registration flow.
    return (
        request.session.get("citizen_id") == citizen_id
        and request.session.get("citizen_ownership") == "registration-v2"
    )


def current_employee(request: Request, db: Session = Depends(get_db)) -> Employee:
    authorization = request.headers.get("Authorization")
    token_password_version = None
    if authorization is not None:
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token or " " in token:
            raise HTTPException(401, "رمز الدخول غير صالح",
                                headers={"WWW-Authenticate": "Bearer"})
        try:
            claims = decode_access_token(token)
            employee_id = int(claims["sub"])
            token_password_version = claims["pwdv"]
            if employee_id < 1 or str(employee_id) != claims["sub"] \
                    or type(token_password_version) is not int:
                raise ValueError("Invalid employee claims")
        except (InvalidTokenError, KeyError, TypeError, ValueError):
            raise HTTPException(401, "رمز الدخول غير صالح أو منتهي الصلاحية",
                                headers={"WWW-Authenticate": "Bearer"})
    else:
        employee_id = request.session.get("employee_id")
    employee = db.get(Employee, employee_id) if employee_id else None
    if not employee:
        raise HTTPException(401, "يرجى تسجيل الدخول",
                            headers={"WWW-Authenticate": "Bearer"})
    if not employee.user or not employee.user.is_active:
        if authorization is None:
            request.session.clear()
        raise HTTPException(401, "الحساب غير مفعل")
    expected_version = (token_password_version if authorization is not None
                        else request.session.get("password_version"))
    if expected_version != employee.password_version:
        if authorization is None:
            request.session.clear()
        raise HTTPException(401, "تغيرت كلمة المرور، يرجى تسجيل الدخول مجددًا",
                            headers={"WWW-Authenticate": "Bearer"})
    return employee


def employee_if_authenticated(request: Request, db: Session) -> Employee | None:
    """Resolve staff auth for mixed citizen/staff routes, if credentials exist."""
    if request.headers.get("Authorization") is None and not request.session.get("employee_id"):
        return None
    return current_employee(request, db)


def authorize_complaint(employee: Employee, complaint, permission="complaints.view"):
    from app.services.access import check_permission
    check_permission(employee, permission, complaint.directorate_id)


def authorize_owner(request: Request, db: Session, complaint):
    """A secret tracking grant never grants the citizen account or its history."""
    if is_bot(request):
        require_bot_owner(request, db, complaint.citizen_id)
    elif not (owns_citizen(request, complaint.citizen_id) or
              complaint.id in request.session.get("tracked_complaints", [])):
        raise HTTPException(403, "يلزم رمز المتابعة السري الخاص بهذه الشكوى")


def authorize_reader(request: Request, db: Session, complaint):
    employee = employee_if_authenticated(request, db)
    if employee and not is_bot(request):
        authorize_complaint(employee, complaint)
    else:
        authorize_owner(request, db, complaint)


def check_login_rate(request: Request):
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = _attempts[key]
    while attempts and now - attempts[0] > 300:
        attempts.popleft()
    if len(attempts) >= 15:
        raise HTTPException(429, "محاولات كثيرة، حاول بعد خمس دقائق")
    attempts.append(now)
