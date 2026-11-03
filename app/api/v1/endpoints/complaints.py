import os
import shutil
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from typing import List
from app.models.complaint import StatusEnum
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.complaint import ComplaintCreate, ComplaintResponse
from app.services.complaint_service import ComplaintService
from app.models.complaint import Complaint, Attachment
from bot.config import BOT_TOKEN
from bot.locales import get_txt

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

async def send_telegram_notification(telegram_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}
    async with aiohttp.ClientSession() as session:
        await session.post(url, json=payload)
@router.patch("/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: int, 
    new_status: StatusEnum, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_status=404, detail="Complaint not found")
    
    complaint.status = new_status
    db.commit()
    
    citizen = complaint.citizen
    if citizen and citizen.telegram_id:
        user_lang = getattr(citizen, 'language', 'ar') or 'ar'
        
        raw_status = new_status.value if hasattr(new_status, 'value') else str(new_status.name)
        status_key = f"status_{raw_status.lower()}"
        
        translated_status = get_txt(user_lang, status_key)
        
        msg_text = get_txt(user_lang, "notification_title", code=complaint.tracking_code, status=translated_status)
        
        background_tasks.add_task(send_telegram_notification, citizen.telegram_id, msg_text)
        
    return {"message": "Status updated successfully", "new_status": new_status}
@router.post("/", response_model=ComplaintResponse)
def create_complaint(complaint_in: ComplaintCreate, db: Session = Depends(get_db)):
    return ComplaintService.create_complaint(db=db, complaint_in=complaint_in)

@router.post("/{complaint_id}/attachments/")
async def upload_complaint_attachment(
    complaint_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    db_attachment = Attachment(
        file_path=file_path,
        file_type=file.content_type or "unknown",
        attachable_type="complaint",
        attachable_id=complaint_id
    )
    db.add(db_attachment)
    db.commit()
    db.refresh(db_attachment)
    
    return {"message": "Attachment uploaded successfully", "file_path": file_path}

@router.get("/citizen/{citizen_id}", response_model=List[ComplaintResponse])
def get_citizen_complaints(citizen_id: int, db: Session = Depends(get_db)):
    complaints = db.query(Complaint).filter(Complaint.citizen_id == citizen_id).all()
    return complaints

@router.get("/{complaint_id}", response_model=ComplaintResponse)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint

@router.get("/", response_model=List[ComplaintResponse])
def get_all_complaints(db: Session = Depends(get_db)):
    return db.query(Complaint).all()

@router.get("/track/{tracking_code}", response_model=ComplaintResponse)
def track_complaint(tracking_code: str, db: Session = Depends(get_db)):
    clean_code = tracking_code.strip().upper()
    complaint = db.query(Complaint).filter(Complaint.tracking_code == clean_code).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint