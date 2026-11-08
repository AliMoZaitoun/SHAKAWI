"""Domain translations. Legacy name columns are Arabic compatibility mirrors."""
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session, object_session
from app.models.access import Directorate, Role, Permission
from app.models.foundations import (
    Language, DirectorateTranslation, RoleTranslation, PermissionTranslation,
)
from app.services.request_context import language_context

TRANSLATIONS = {
    "roles": (Role, RoleTranslation, "role_id"),
    "permissions": (Permission, PermissionTranslation, "permission_code"),
    "directorates": (Directorate, DirectorateTranslation, "directorate_id"),
}


def localized(row, language=None):
    db = object_session(row)
    fields = ("name", "description", "location") if isinstance(row, Directorate) else ("name", "description")
    result = {field: getattr(row, field) for field in fields}
    if db is None:
        return result
    _, model, key = next(value for value in TRANSLATIONS.values() if isinstance(row, value[0]))
    identifier = row.code if isinstance(row, Permission) else row.id
    choices = db.query(model).join(Language, model.language_code == Language.code).filter(
        getattr(model, key) == identifier, Language.is_active.is_(True),
    ).order_by(model.language_code).all()
    by_code = {value.language_code: value for value in choices}
    selected = by_code.get(language or language_context.get()) or by_code.get("ar")
    if selected is None and choices:
        selected = choices[0]
    if selected:
        result = {field: getattr(selected, field) for field in fields}
    return result


def seed_translations(db):
    from app.services.translation_defaults import ENGLISH_PERMISSIONS, ENGLISH_ROLES
    for code, name, direction in (("ar", "العربية", "rtl"), ("en", "English", "ltr")):
        if not db.get(Language, code):
            db.add(Language(code=code, name=name, direction=direction))
    db.flush()
    for parent, model, key in TRANSLATIONS.values():
        for row in db.query(parent):
            identifier = row.code if parent is Permission else row.id
            if not db.get(model, (identifier, "ar")):
                fields = {field: getattr(row, field) for field in
                          (("name", "description", "location") if parent is Directorate else ("name", "description"))}
                db.add(model(**{key: identifier}, language_code="ar", **fields))
            english = (
                ENGLISH_ROLES.get(row.code) if parent is Role else
                ENGLISH_PERMISSIONS.get(row.code) if parent is Permission else
                {"المحافظة": "Governorate", "الخدمات": "Services"}.get(row.name)
            )
            if english and not db.get(model, (identifier, "en")):
                fields = {"name": english, "description": ""}
                if parent is Directorate:
                    fields["location"] = ""
                db.add(model(**{key: identifier}, language_code="en", **fields))
    db.flush()


@event.listens_for(Session, "after_flush_postexec")
def sync_arabic_mirrors(db, context):
    pending = db.info.pop("arabic_translations", [])
    for row in pending:
        _, model, key = next(value for value in TRANSLATIONS.values() if isinstance(row, value[0]))
        identifier = row.code if isinstance(row, Permission) else row.id
        if not db.get(Language, "ar") and not any(isinstance(value, Language) and value.code == "ar" for value in db.new):
            db.add(Language(code="ar", name="العربية", direction="rtl"))
        translation = db.get(model, (identifier, "ar"))
        fields = ("name", "description", "location") if isinstance(row, Directorate) else ("name", "description")
        if translation is None:
            translation = model(**{key: identifier}, language_code="ar")
            db.add(translation)
        for field in fields:
            setattr(translation, field, getattr(row, field) or "")


@event.listens_for(Session, "before_flush")
def capture_arabic_mirrors(db, context, instances):
    parents = tuple(value[0] for value in TRANSLATIONS.values())
    for row in list(db.new) + list(db.dirty):
        if isinstance(row, parents) and row not in db.deleted:
            fields = ("name", "description", "location") if isinstance(row, Directorate) else ("name", "description")
            if row in db.new or any(inspect(row).attrs[field].history.has_changes() for field in fields):
                db.info.setdefault("arabic_translations", []).append(row)
