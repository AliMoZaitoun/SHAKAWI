"""Transactional audit allowlists: never log bodies, passwords or recovery tokens."""
from enum import Enum
from uuid import uuid4
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from app.models.access import AccessAudit, Role, RoleAssignment, User, Directorate, Permission
from app.models.complaint import (
    Complaint, ComplaintNote, EvidenceRequest, EvidenceReply, PublicComplaintReview,
    Attachment, EvidenceFile,
)
from app.models.foundations import (
    AuditEvent, ComplaintHistory, Language, RoleTranslation, PermissionTranslation,
    DirectorateTranslation,
)
from app.models.recovery import RecoveryKey, OwnershipChallenge
from app.models.user import Citizen
from app.services.request_context import request_context

# No free-text complaint/note/evidence/identity/profile fields.
FIELDS = {
    Complaint: ("status", "directorate_id", "progress", "priority", "is_public", "public_text_hidden"),
    ComplaintNote: ("audience", "is_internal", "notification_status"),
    EvidenceRequest: ("complaint_id", "status", "notification_status"),
    EvidenceReply: ("request_id", "channel"),
    PublicComplaintReview: ("complaint_id", "action"),
    Attachment: ("attachable_type", "attachable_id"),
    EvidenceFile: ("reply_id",),
    Role: ("code", "is_system"),
    RoleAssignment: ("employee_id", "role_id", "scope_type", "directorate_id"),
    User: ("user_type", "is_active", "needs_profile_completion"),
    Directorate: ("is_active",),
    Permission: ("code",),
    Language: ("code", "is_active", "direction"),
    RoleTranslation: ("role_id", "language_code"),
    PermissionTranslation: ("permission_code", "language_code"),
    DirectorateTranslation: ("directorate_id", "language_code"),
    Citizen: ("user_id",),  # Telegram changes are recorded as a flag, not an ID.
    RecoveryKey: (),
    OwnershipChallenge: (),
    AccessAudit: ("action", "target_type", "target_id"),
}


def primitive(value):
    return value.value if isinstance(value, Enum) else value


def record_event(db, action, entity_type, entity_id, *, actor_user_id=None):
    """Explicit safe event for atomic bulk SQL or authentication (no payload)."""
    meta = request_context.get()
    db.add(AuditEvent(
        actor_user_id=actor_user_id if actor_user_id is not None else meta.get("actor_user_id"),
        action=action, entity_type=entity_type, entity_id=str(entity_id), changes={},
        source=meta.get("source", "system"), request_id=meta.get("request_id") or str(uuid4()),
    ))


@event.listens_for(Session, "before_flush")
def capture_changes(db, context, instances):
    for row in list(db.dirty) + list(db.deleted):
        if isinstance(row, (AuditEvent, ComplaintHistory)):
            raise ValueError("Audit and history records are append-only")
    if db.info.get("disable_audit"):
        return
    for row in list(db.new) + list(db.dirty) + list(db.deleted):
        fields = FIELDS.get(type(row))
        if fields is None:
            continue
        state = inspect(row)
        operation = "create" if row in db.new else "delete" if row in db.deleted else "update"
        changes = {}
        for field in fields:
            history = state.attrs[field].history
            if operation != "update" or history.has_changes():
                changes[field] = {
                    "old": primitive(history.deleted[0]) if history.deleted else None,
                    "new": None if operation == "delete" else primitive(getattr(row, field)),
                }
        # Explicit flags instead of secret values or PII.
        special = {User: ("hashed_password", "first_name", "last_name", "phone", "email"),
                   Citizen: ("telegram_id", "identity_card_url"),
                   Role: ("name", "description", "permissions")}
        for field in special.get(type(row), ()):
            if operation == "update" and state.attrs[field].history.has_changes():
                changes[field + "_changed"] = True
        if isinstance(row, Role):
            history = state.attrs.permissions.history
            if operation == "create" or history.has_changes():
                current = {permission.code for permission in row.permissions}
                previous = (current - {permission.code for permission in history.added}) | {
                    permission.code for permission in history.deleted}
                changes["permissions"] = {"old": sorted(previous) if operation != "create" else [],
                                          "new": sorted(current)}
        if operation == "update" and not changes:
            # Translation text and private reply content are intentionally omitted.
            if not db.is_modified(row, include_collections=False):
                continue
        db.info.setdefault("audit_pending", []).append((row, operation, changes))


@event.listens_for(Session, "after_flush_postexec")
def persist_changes(db, context):
    conn = db.connection()
    meta = request_context.get()
    actor = meta.get("actor_user_id")
    source = meta.get("source", "system")
    request_id = meta.get("request_id") or str(uuid4())
    for row, operation, changes in db.info.pop("audit_pending", []):
        state = inspect(row)
        identifier = ":".join(str(value) for value in (state.identity or ("unknown",)))
        if isinstance(row, (OwnershipChallenge, RecoveryKey)):
            identifier = str(row.citizen_id)
        action = f"{row.__tablename__}.{operation}"
        if isinstance(row, AccessAudit):
            action = row.action
        conn.execute(AuditEvent.__table__.insert().values(
            actor_user_id=actor, action=action, entity_type=row.__tablename__,
            entity_id=identifier, changes=changes, source=source, request_id=request_id,
        ))
        if isinstance(row, Complaint) and operation != "delete" and (
            operation == "create" or any(key in changes for key in ("status", "directorate_id", "progress"))
        ):
            conn.execute(ComplaintHistory.__table__.insert().values(
                complaint_id=row.id, actor_user_id=actor,
                event="created" if operation == "create" else "processing_changed",
                old_status=changes.get("status", {}).get("old") if "status" in changes else (
                    primitive(row.status) if operation != "create" else None),
                new_status=primitive(row.status),
                old_directorate_id=changes.get("directorate_id", {}).get("old") if "directorate_id" in changes else (
                    row.directorate_id if operation != "create" else None),
                new_directorate_id=row.directorate_id,
                old_progress=changes.get("progress", {}).get("old") if "progress" in changes else (
                    row.progress if operation != "create" else None),
                new_progress=row.progress, reason=db.info.get("history_reason", ""),
                source=source, request_id=request_id,
            ))


def record_security_failure(request_id, source, status):
    # This logger is separate from the rolled-back business transaction.
    import logging
    logging.getLogger("security.events").warning(
        "access_denied request_id=%s source=%s status=%s", request_id, source, status,
    )
