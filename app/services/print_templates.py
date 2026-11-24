from sqlalchemy.orm import Session

from app.models.foundations import PrintTemplateSettings

PRINT_SECTION_IDS = {
    "tracking_code",
    "title",
    "details",
    "directorate",
    "category",
    "created_at",
    "status",
    "progress",
    "resolution_report",
    "public_updates",
    "citizen_contact",
}
DEFAULT_PRINT_SECTIONS = [
    "tracking_code",
    "title",
    "details",
    "directorate",
    "category",
    "created_at",
    "status",
    "progress",
    "resolution_report",
    "public_updates",
]
DEFAULT_PRINT_TITLES = {"ar": "ملخص الشكوى", "en": "Complaint summary"}


def bootstrap_print_template(db: Session) -> PrintTemplateSettings:
    row = db.get(PrintTemplateSettings, 1)
    if row is None:
        row = PrintTemplateSettings(
            id=1,
            titles=DEFAULT_PRINT_TITLES,
            default_sections=DEFAULT_PRINT_SECTIONS,
        )
        db.add(row)
        db.flush()
    return row


def get_print_template(db: Session) -> PrintTemplateSettings:
    return db.get(PrintTemplateSettings, 1) or bootstrap_print_template(db)


def print_template_data(db: Session) -> dict:
    row = get_print_template(db)
    return {
        "titles": row.titles or DEFAULT_PRINT_TITLES,
        "default_sections": row.default_sections or DEFAULT_PRINT_SECTIONS,
        "updated_at": row.updated_at,
    }
