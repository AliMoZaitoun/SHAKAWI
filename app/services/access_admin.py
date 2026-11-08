"""Transactional admin helpers: serialized grants, audit, and safe serializers."""
import json

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.models.access import AccessAudit, Directorate, Permission, Role
from app.services.access import assert_admin_survives, check_permission


def begin_change(db, actor, permission="rbac.manage"):
    # Serializes all security mutations even on SQLite (FOR UPDATE is ignored
    # there). The same shared row is locked on PostgreSQL as well.
    db.execute(update(Role).where(Role.code == "governor").values(name=Role.name))
    db.expire_all()
    check_permission(actor, permission, global_only=True)


def finish_change(db, actor, action, target_type, target_id, details=None):
    try:
        assert_admin_survives(db)
        db.add(AccessAudit(actor_id=actor.id, action=action, target_type=target_type,
                           target_id=str(target_id), details=json.dumps(details or {}, ensure_ascii=False)))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "تعارض مع سجل موجود أو علاقة مستخدمة")
    except Exception:
        db.rollback()
        raise


def permission_rows(db, codes):
    unique = set(codes)
    rows = db.query(Permission).filter(Permission.code.in_(unique)).all()
    if len(rows) != len(unique):
        raise HTTPException(422, "توجد صلاحية غير معرّفة ضمن كتالوج العمليات المدعومة")
    return rows


def directorate_or_422(db, identifier, *, active=True):
    if identifier is None:
        return None
    row = db.get(Directorate, identifier)
    if not row or (active and not row.is_active):
        raise HTTPException(422, "المديرية غير موجودة أو غير مفعلة")
    return row


def role_data(role):
    from app.services.translations import localized
    return {"id": role.id, "code": role.code, **localized(role), "is_system": role.is_system,
            "permissions": sorted(permission.code for permission in role.permissions)}


def assignment_data(row):
    return {"id": row.id, "employee_id": row.employee_id, "role_id": row.role_id,
            "scope_type": row.scope_type, "directorate_id": row.directorate_id}


def employee_data(employee):
    user = employee.user
    return {"id": employee.id, "user_id": employee.user_id, "username": employee.username,
            "first_name": user.first_name, "last_name": user.last_name,
            "phone": user.phone, "email": user.email, "is_active": user.is_active,
            "directorate_id": employee.directorate_id,
            "needs_profile_completion": user.needs_profile_completion,
            "role_assignments": [assignment_data(row) for row in employee.role_assignments]}
