"""Mark imported state honestly; do not invent historical transitions."""
import json
from sqlalchemy import select
from app.models.complaint import Complaint
from app.models.access import AccessAudit
from app.models.user import Employee
from app.models.foundations import AuditEvent, ComplaintHistory


def backfill_history(db):
    conn = db.connection()
    for complaint in db.query(Complaint):
        if not conn.execute(select(ComplaintHistory.id).where(
            ComplaintHistory.complaint_id == complaint.id
        )).first():
            conn.execute(ComplaintHistory.__table__.insert().values(
                complaint_id=complaint.id, event="imported_snapshot",
                new_status=complaint.status.value, new_directorate_id=complaint.directorate_id,
                new_progress=complaint.progress, reason="", source="migration",
                request_id="legacy-baseline",
            ))
    for row in db.query(AccessAudit):
        identifier = f"legacy-access-{row.id}"
        if not conn.execute(select(AuditEvent.id).where(AuditEvent.request_id == identifier)).first():
            actor = db.get(Employee, row.actor_id)
            # Only structured IDs/flags from the old administrator allowlist.
            try:
                details = json.loads(row.details)
            except (ValueError, TypeError):
                details = {}
            safe = {key: value for key, value in details.items() if key in {
                "employee_id", "role_id", "scope_key", "permissions", "fields",
            }}
            conn.execute(AuditEvent.__table__.insert().values(
                actor_user_id=actor.user_id if actor else None, action=row.action,
                entity_type=row.target_type, entity_id=row.target_id, changes=safe,
                source="migration", request_id=identifier, created_at=row.created_at,
            ))
