"""Language/translation management independent of future React presentation."""
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.foundations import Language, UserLanguage
from app.core.security import current_employee, employee_if_authenticated, owns_citizen
from app.models.user import Citizen
from app.services.access import require_permission
from app.services.access_admin import begin_change, finish_change
from app.services.translations import TRANSLATIONS

router = APIRouter()
manage = require_permission("rbac.manage", global_only=True)


class LanguageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(pattern=r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$", max_length=35)
    name: str = Field(min_length=1, max_length=100)
    direction: Literal["ltr", "rtl"] = "ltr"
    is_active: bool = True


class LanguageEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    direction: Literal["ltr", "rtl"]
    is_active: bool = True


class TranslationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=4000)
    location: str | None = Field(default=None, max_length=500)


def language_row(db, code):
    row = db.get(Language, code)
    if not row or not row.is_active:
        raise HTTPException(422, "اللغة غير موجودة أو غير مفعلة")
    return row


@router.get("/languages")
def languages(db: Session = Depends(get_db)):
    return [{"code": row.code, "name": row.name, "direction": row.direction}
            for row in db.query(Language).filter_by(is_active=True).order_by(Language.code)]


@router.get("/admin/languages")
def admin_languages(actor=Depends(manage), db: Session = Depends(get_db)):
    return [{"code": row.code, "name": row.name, "direction": row.direction, "is_active": row.is_active}
            for row in db.query(Language).order_by(Language.code)]


@router.post("/admin/languages", status_code=201)
def create_language(data: LanguageInput, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    if db.get(Language, data.code):
        raise HTTPException(409, "اللغة موجودة مسبقاً")
    if data.code == "ar" and not data.is_active:
        raise HTTPException(409, "العربية هي لغة الرجوع ولا يمكن تعطيلها")
    db.add(Language(**data.model_dump()))
    finish_change(db, actor, "language.create", "language", data.code)
    return data.model_dump()


@router.put("/admin/languages/{code}")
def edit_language(code: str, data: LanguageEdit, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    row = db.get(Language, code)
    if not row:
        raise HTTPException(404, "اللغة غير موجودة")
    if code == "ar" and not data.is_active:
        raise HTTPException(409, "لا يمكن تعطيل لغة الرجوع العربية")
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    finish_change(db, actor, "language.update", "language", code)
    return {"code": code, **data.model_dump()}


def translation_parent(db, entity, identifier):
    parent, model, key = TRANSLATIONS[entity]
    if entity != "permissions":
        try:
            identifier = int(identifier)
        except ValueError:
            raise HTTPException(422, "معرّف السجل غير صالح")
    row = db.get(parent, identifier)
    if not row:
        raise HTTPException(404, "السجل غير موجود")
    return row, model, key, identifier


@router.get("/admin/translations/{entity}/{identifier}")
def translations(entity: Literal["roles", "permissions", "directorates"], identifier: str,
                 actor=Depends(manage), db: Session = Depends(get_db)):
    _, model, key, identifier = translation_parent(db, entity, identifier)
    fields = ("language_code", "name", "description", "location") if entity == "directorates" else (
        "language_code", "name", "description")
    return [{field: getattr(row, field) for field in fields}
            for row in db.query(model).filter(getattr(model, key) == identifier).order_by(model.language_code)]


@router.put("/admin/translations/{entity}/{identifier}/{language}")
def put_translation(entity: Literal["roles", "permissions", "directorates"], identifier: str,
                    language: str, data: TranslationInput, actor=Depends(manage),
                    db: Session = Depends(get_db)):
    begin_change(db, actor)
    language_row(db, language)
    parent, model, key, identifier = translation_parent(db, entity, identifier)
    if entity != "directorates" and data.location is not None:
        raise HTTPException(422, "الموقع خاص بالمديريات")
    row = db.get(model, (identifier, language))
    if not row:
        row = model(**{key: identifier}, language_code=language)
        db.add(row)
    fields = ("name", "description", "location") if entity == "directorates" else ("name", "description")
    for field in fields:
        value = getattr(data, field) or ""
        setattr(row, field, value)
        if language == "ar":
            setattr(parent, field, value)
    finish_change(db, actor, "translation.update", entity, identifier, {"language": language})
    return {"language_code": language, **{field: getattr(row, field) for field in fields}}


@router.delete("/admin/translations/{entity}/{identifier}/{language}")
def delete_translation(entity: Literal["roles", "permissions", "directorates"], identifier: str,
                       language: str, actor=Depends(manage), db: Session = Depends(get_db)):
    begin_change(db, actor)
    if language == "ar":
        raise HTTPException(409, "لا يمكن حذف الترجمة العربية الأساسية")
    _, model, _, identifier = translation_parent(db, entity, identifier)
    row = db.get(model, (identifier, language))
    if not row:
        raise HTTPException(404, "الترجمة غير موجودة")
    db.delete(row)
    finish_change(db, actor, "translation.delete", entity, identifier, {"language": language})
    return {"ok": True}


class PreferenceInput(BaseModel):
    language_code: str = Field(max_length=35)


@router.put("/language-preference")
def set_preference(data: PreferenceInput, request: Request, db: Session = Depends(get_db)):
    language_row(db, data.language_code)
    employee = employee_if_authenticated(request, db)
    if employee:
        user_id = employee.user_id
    else:
        citizen_id = request.session.get("citizen_id")
        if not citizen_id or not owns_citizen(request, citizen_id):
            raise HTTPException(403, "يلزم إثبات ملكية الحساب")
        user_id = db.get(Citizen, citizen_id).user_id
    row = db.get(UserLanguage, user_id)
    if row:
        row.language_code = data.language_code
    else:
        db.add(UserLanguage(user_id=user_id, language_code=data.language_code))
    db.commit()
    return {"language_code": data.language_code}
