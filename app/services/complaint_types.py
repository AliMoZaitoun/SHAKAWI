"""Shared complaint-type catalog, localization, and safe bootstrap defaults."""
from app.models.complaint import ComplaintType
from app.services.translations import localized


DEFAULT_COMPLAINT_TYPES = (
    ("roads", "طرق"),
    ("building_violations", "مخالفات بناء"),
    ("excavations", "حفريات"),
    ("road_opening", "فتح طرق"),
    ("service_outage", "انقطاع خدمة"),
    ("technical_issue", "عطل فني"),
    ("administrative_complaint", "شكوى إدارية"),
    ("other", "أخرى"),
)


def bootstrap_complaint_types(db):
    """Seed existing selectable categories without inventing SLA policies."""
    for code, name in DEFAULT_COMPLAINT_TYPES:
        if db.query(ComplaintType).filter_by(code=code).first():
            continue
        db.add(ComplaintType(
            code=code,
            name=name,
            description="",
            sla_duration_minutes=None,
            is_active=True,
            is_system=(code == "other"),
        ))
    db.flush()


def complaint_type_data(row, language=None):
    values = localized(row, language)
    return {
        "id": row.id,
        "code": row.code,
        "name": values["name"],
        "description": values["description"],
        "sla_duration_minutes": row.sla_duration_minutes,
        "is_active": row.is_active,
        "is_system": row.is_system,
    }


def complaint_snapshot_data(complaint, language=None):
    if not complaint.complaint_type:
        return None
    data = complaint_type_data(complaint.complaint_type, language)
    # The estimate belongs to the complaint at submission time, so a later
    # catalog edit cannot silently change an existing citizen's expectation.
    data["sla_duration_minutes"] = complaint.sla_duration_minutes
    return data


def complaint_category_label(complaint, language=None):
    if complaint.complaint_type:
        return localized(complaint.complaint_type, language)["name"]
    return complaint.category
