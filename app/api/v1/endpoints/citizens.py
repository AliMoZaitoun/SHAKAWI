from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import is_bot, owns_citizen, require_bot
from app.db.session import get_db
from app.models.user import Citizen
from app.schemas.user import CitizenCreate, CitizenResponse
from app.services.uploads import save_upload

router = APIRouter()


@router.get("/telegram/{telegram_id}", response_model=CitizenResponse, dependencies=[Depends(require_bot)])
def by_telegram(telegram_id: int, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter_by(telegram_id=telegram_id).first()
    if not citizen:
        raise HTTPException(404, "المواطن غير موجود")
    return citizen


@router.get("/phone/{phone}", response_model=CitizenResponse, dependencies=[Depends(require_bot)])
def by_phone(phone: str, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter_by(phone=phone).first()
    if not citizen:
        raise HTTPException(404, "المواطن غير موجود")
    return citizen


@router.post("/", response_model=CitizenResponse)
def create(data: CitizenCreate, request: Request, db: Session = Depends(get_db)):
    trusted_bot = is_bot(request)
    if data.telegram_id is not None and not trusted_bot:
        raise HTTPException(403, "ربط تيليغرام متاح من خلال البوت فقط")
    existing = db.query(Citizen).filter(
        (Citizen.phone == data.phone) | (Citizen.national_id == data.national_id)
    ).first()
    if existing:
        if not trusted_bot and not owns_citizen(request, existing.id):
            raise HTTPException(
                409,
                "هذا السجل موجود مسبقًا. البيانات الشخصية وحدها لا تثبت ملكيته. "
                "استخدم جلسة التسجيل الأصلية أو حساب تيليغرام المرتبط به، "
                "أو راجع الجهة المختصة للتحقق من الملكية.",
            )
        # Never disclose or overwrite another citizen's identity via an OR match.
        if (existing.phone != data.phone or existing.national_id != data.national_id
                or existing.first_name != data.first_name or existing.last_name != data.last_name):
            raise HTTPException(409, "البيانات لا تطابق السجل الحالي، يرجى مراجعتها")
        if trusted_bot and data.telegram_id:
            if existing.telegram_id != data.telegram_id:
                raise HTTPException(409, "يلزم التحقق من ملكية السجل قبل ربط حساب تيليغرام جديد")
        citizen = existing
    else:
        citizen = Citizen(**data.model_dump(exclude_none=True, exclude={"identity_card_url"}))
        db.add(citizen)
    try:
        db.commit()
        db.refresh(citizen)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "يوجد سجل بهذه البيانات")
    if not trusted_bot:
        request.session["citizen_id"] = citizen.id
        request.session["citizen_ownership"] = "registration-v2"
    return citizen


@router.post("/{citizen_id}/id-image/")
async def identity_image(citizen_id: int, request: Request, file: UploadFile = File(...),
                         db: Session = Depends(get_db)):
    if not is_bot(request) and not owns_citizen(request, citizen_id):
        raise HTTPException(403, "لا تملك صلاحية تعديل هوية هذا المواطن")
    citizen = db.get(Citizen, citizen_id)
    if not citizen:
        raise HTTPException(404, "المواطن غير موجود")
    citizen.identity_card_url = await save_upload(file, identity=True)
    db.commit()
    return {"message": "تم حفظ صورة الهوية", "file_path": citizen.identity_card_url}
