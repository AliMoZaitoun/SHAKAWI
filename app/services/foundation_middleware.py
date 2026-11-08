"""Resolve language and safe audit context once per request."""
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from app.models.foundations import Language, UserLanguage
from app.models.user import Citizen, Employee
from app.services.request_context import language_context, request_context


def header_languages(header):
    choices = []
    for index, item in enumerate(header.split(",")):
        parts = item.strip().split(";")
        try:
            quality = float(parts[1].strip().removeprefix("q=")) if len(parts) > 1 else 1
        except ValueError:
            continue
        if 0 < quality <= 1:
            choices.append((-quality, index, parts[0].lower()))
    return [code for _, _, code in sorted(choices)]


class FoundationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        from app.db.session import SessionLocal
        # Honor dependency overrides in isolated API tests without touching live data.
        from app.db.session import get_db
        override = request.app.dependency_overrides.get(get_db)
        iterator = override() if override else None
        db = next(iterator) if iterator else SessionLocal()
        actor = preferred = None
        try:
            employee = db.get(Employee, request.session.get("employee_id")) if request.session.get("employee_id") else None
            if employee and employee.user and employee.user.is_active and (
                request.session.get("password_version") == employee.password_version
            ):
                actor = employee.user_id
            elif request.session.get("citizen_ownership") and request.session.get("citizen_id"):
                citizen = db.get(Citizen, request.session["citizen_id"])
                actor = citizen.user_id if citizen else None
            if actor:
                preference = db.get(UserLanguage, actor)
                preferred = preference.language_code if preference else None
            available = {row.code for row in db.query(Language).filter_by(is_active=True)}
            candidates = [request.query_params.get("lang", "").lower(), preferred]
            candidates.extend(header_languages(request.headers.get("Accept-Language", "")))
            language = "ar"
            for code in candidates:
                if code in available:
                    language = code
                    break
                if code and code.split("-")[0] in available:
                    language = code.split("-")[0]
                    break
        finally:
            if iterator:
                iterator.close()
            else:
                db.close()
        from app.core.security import is_bot
        source = "telegram" if is_bot(request) else "web"
        context_token = request_context.set(dict(
            actor_user_id=actor, source=source, request_id=str(uuid4()),
        ))
        language_token = language_context.set(language)
        try:
            response = await call_next(request)
            response.headers["Content-Language"] = language
            response.headers["X-Request-ID"] = request_context.get()["request_id"]
            if response.status_code in (401, 403, 429):
                from app.services.audit import record_security_failure
                record_security_failure(request_context.get()["request_id"], source, response.status_code)
            return response
        finally:
            request_context.reset(context_token)
            language_context.reset(language_token)
