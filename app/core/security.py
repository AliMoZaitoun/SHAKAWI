"""Password hashing and authorization for the imported employee accounts."""
import base64
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import Citizen, Employee, UserRole

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
    if not db.query(Citizen).filter_by(id=citizen_id, telegram_id=telegram_id).first():
        raise HTTPException(403, "لم يعد حساب تيليغرام مرتبطًا بهذا السجل")


def owns_citizen(request: Request, citizen_id: int) -> bool:
    # Only newly registered browser sessions get this capability. A replay of
    # someone else's personal details must never issue it. Versioning also
    # rejects old cookies issued by the previously permissive registration flow.
    return (
        request.session.get("citizen_id") == citizen_id
        and request.session.get("citizen_ownership") == "registration-v2"
    )


def current_employee(request: Request, db: Session = Depends(get_db)) -> Employee:
    employee = db.get(Employee, request.session.get("employee_id")) if request.session.get("employee_id") else None
    if not employee:
        raise HTTPException(401, "يرجى تسجيل الدخول")
    if request.session.get("password_version") != employee.password_version:
        request.session.clear()
        raise HTTPException(401, "تغيرت كلمة المرور، يرجى تسجيل الدخول مجددًا")
    return employee


def authorize_complaint(employee: Employee, complaint):
    if employee.role != UserRole.GOVERNOR and complaint.directorate_id != employee.directorate_id:
        raise HTTPException(403, "لا تملك صلاحية الوصول إلى هذه الشكوى")


def check_login_rate(request: Request):
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts = _attempts[key]
    while attempts and now - attempts[0] > 300:
        attempts.popleft()
    if len(attempts) >= 15:
        raise HTTPException(429, "محاولات كثيرة، حاول بعد خمس دقائق")
    attempts.append(now)
