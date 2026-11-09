"""Permission catalog, conservative legacy grants, and live scope evaluation."""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import object_session

from app.models.access import Directorate, Permission, Role, RoleAssignment
from app.models.user import Employee, UserRole

PERMISSIONS = {
    "complaints.view": "عرض الشكاوى",
    "complaints.update": "تحديث معالجة الشكاوى",
    "complaints.resolve": "إغلاق الشكاوى كمحلولة",
    "complaints.files.read": "تنزيل مرفقات الشكوى",
    "complaints.notes.create": "إضافة ملاحظات الشكوى",
    "notifications.retry": "إعادة محاولة الإشعارات",
    "evidence.request": "طلب استكمال الأدلة",
    "evidence.read": "قراءة مراسلات الأدلة",
    "evidence.files.read": "تنزيل ملفات الأدلة",
    "public.review": "مراجعة بلاغات النصوص العامة",
    "reports.view": "عرض إحصائيات الشكاوى",
    "rbac.manage": "إدارة الأدوار والصلاحيات وإسنادها",
    "employees.manage": "إدارة حسابات الموظفين",
    "directorates.manage": "إدارة المديريات",
    "audit.view": "عرض سجل تدقيق النظام",
    "files.identity.read": "قراءة وثائق الهوية",
    "complaints.transfer": "تحويل الشكاوى بين المديريات",
}
ADMIN_PERMISSIONS = {"rbac.manage", "employees.manage", "directorates.manage",
                     "audit.view", "files.identity.read"}


def bootstrap_access(db):
    """Seed definitions, not an unapproved permission matrix for the new roles."""
    for code, name in PERMISSIONS.items():
        if not db.get(Permission, code):
            db.add(Permission(code=code, name=name))
    db.flush()
    definitions = [
        ("governor", "المحافظ", set(PERMISSIONS)),
        ("technical_assistant", "المساعد التقني", set()),
        ("complaint_receiver", "مستلم الشكاوى", set()),
        ("branch_manager", "مدير الفرع", set()),
        ("legacy_department_staff", "صلاحيات موظف الفرع السابقة", set(PERMISSIONS) - ADMIN_PERMISSIONS),
    ]
    roles = {}
    for code, name, permissions in definitions:
        role = db.query(Role).filter_by(code=code).first()
        if role is None:
            role = Role(code=code, name=name, is_system=True)
            role.permissions = [db.get(Permission, permission) for permission in sorted(permissions)]
            db.add(role)
            db.flush()
        roles[code] = role
    for employee in db.query(Employee).filter_by(rbac_initialized=False).all():
        if employee.role == UserRole.GOVERNOR:
            db.add(RoleAssignment(employee=employee, role=roles["governor"],
                                  scope_type="global", scope_key=0))
        elif employee.role == UserRole.EMPLOYEE and employee.directorate_id:
            db.add(RoleAssignment(employee=employee, role=roles["legacy_department_staff"],
                                  scope_type="directorate", directorate_id=employee.directorate_id,
                                  scope_key=employee.directorate_id))
        employee.rbac_initialized = True
    db.commit()


def permission_scopes(employee, permission):
    """None is global; directorate grants flow down the active tree only."""
    if not employee.user or not employee.user.is_active:
        return set()
    assigned_scopes = set()
    for assignment in employee.role_assignments:
        if not any(item.code == permission for item in assignment.role.permissions):
            continue
        if assignment.scope_type == "global":
            return None
        if assignment.directorate_id:
            assigned_scopes.add(assignment.directorate_id)
    if not assigned_scopes:
        return set()

    db = object_session(employee)
    if db is None:
        # Detached objects fail closed to their explicit assignments.
        return assigned_scopes

    active_ids = set()
    children_by_parent = {}
    for directorate_id, parent_id, is_active in db.query(
        Directorate.id, Directorate.parent_id, Directorate.is_active
    ).all():
        if not is_active:
            continue
        active_ids.add(directorate_id)
        if parent_id is not None:
            children_by_parent.setdefault(parent_id, []).append(directorate_id)

    scopes = set()
    pending = [identifier for identifier in assigned_scopes if identifier in active_ids]
    while pending:
        directorate_id = pending.pop()
        if directorate_id in scopes:
            continue
        scopes.add(directorate_id)
        pending.extend(children_by_parent.get(directorate_id, ()))
    return scopes


def check_permission(employee, permission, directorate_id=None, *, global_only=False):
    scopes = permission_scopes(employee, permission)
    allowed = scopes is None or (
        not global_only and bool(scopes)
        and (directorate_id is None or directorate_id in scopes)
    )
    if not allowed:
        raise HTTPException(403, "لا تملك الصلاحية المطلوبة ضمن هذا النطاق")


def has_permission(employee, permission, directorate_id):
    scopes = permission_scopes(employee, permission)
    return scopes is None or directorate_id in scopes


def scope_query(query, model, employee, permission):
    check_permission(employee, permission)
    scopes = permission_scopes(employee, permission)
    return query if scopes is None else query.filter(model.directorate_id.in_(scopes))


def require_permission(permission, *, global_only=False):
    # Local import avoids a security/authorization dependency cycle.
    from app.core.security import current_employee

    def dependency(employee=Depends(current_employee)):
        check_permission(employee, permission, global_only=global_only)
        return employee
    return dependency


def assert_admin_survives(db):
    """Changes are flushed before this check and rolled back on failure."""
    db.flush()
    for employee in db.query(Employee).all():
        # Flush/expire prevents a just-deleted grant surviving in a relationship.
        db.expire(employee, ["role_assignments"])
        if permission_scopes(employee, "rbac.manage") is None:
            return
    raise HTTPException(409, "لا يمكن إلغاء أو تعطيل آخر حساب فعال لإدارة الصلاحيات")
