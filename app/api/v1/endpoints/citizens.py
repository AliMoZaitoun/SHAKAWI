import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.user import CitizenCreate, CitizenResponse
from app.models.user import Citizen

router = APIRouter(prefix="", tags=["Citizens"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/telegram/{telegram_id}", response_model=CitizenResponse)
def get_citizen_by_telegram(telegram_id: int, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter(Citizen.telegram_id == telegram_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return citizen


@router.get("/phone/{phone}", response_model=CitizenResponse)
def get_citizen_by_phone(phone: str, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter(Citizen.phone == phone).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")
    return citizen


@router.post("/", response_model=CitizenResponse)
def create_citizen(citizen_in: CitizenCreate, db: Session = Depends(get_db)):
    existing_citizen = db.query(Citizen).filter(
        (Citizen.phone == citizen_in.phone) | (Citizen.national_id == citizen_in.national_id)
    ).first()
    
    if existing_citizen:
        if not existing_citizen.telegram_id:
            existing_citizen.telegram_id = citizen_in.telegram_id
            db.commit()
            db.refresh(existing_citizen)
        return existing_citizen

    db_citizen = Citizen(
        first_name=citizen_in.first_name,
        last_name=citizen_in.last_name,
        phone=citizen_in.phone,
        national_id=citizen_in.national_id,
        telegram_id=citizen_in.telegram_id
    )
    db.add(db_citizen)
    db.commit()
    db.refresh(db_citizen)
    return db_citizen

@router.post("/{citizen_id}/id-image/")
async def upload_citizen_id_card(
    citizen_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # التأكد من وجود المواطن أولاً
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")

    file_extension = file.filename.split('.')[-1] if '.' in file.filename else "jpg"
    file_path = os.path.join(UPLOAD_DIR, f"citizen_{citizen_id}_id.{file_extension}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"message": "ID card uploaded successfully", "file_path": file_path}