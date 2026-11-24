from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.print_template import PrintTemplateInput
from app.services.access import require_permission
from app.services.audit import record_event
from app.services.print_templates import get_print_template, print_template_data

router = APIRouter()
manage = require_permission("branding.manage", global_only=True)


@router.get("/print-template")
def public_print_template(db: Session = Depends(get_db)):
    return print_template_data(db)


@router.get("/admin/settings/print-template")
def read_print_template(actor=Depends(manage), db: Session = Depends(get_db)):
    return print_template_data(db)


@router.put("/admin/settings/print-template")
def save_print_template(
    data: PrintTemplateInput,
    actor=Depends(manage),
    db: Session = Depends(get_db),
):
    row = get_print_template(db)
    # Keep title translations for languages not present in this editor.
    row.titles = {**(row.titles or {}), **data.titles}
    row.default_sections = data.default_sections
    row.updated_by_user_id = actor.user.id if actor.user else None
    record_event(
        db, "print_template.defaults_updated", "print_template_settings", "1",
        actor_user_id=actor.user.id if actor.user else None,
    )
    db.commit()
    return print_template_data(db)
