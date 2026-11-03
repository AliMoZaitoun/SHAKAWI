import random
import string
from sqlalchemy.orm import Session
from app.models.complaint import Complaint, Attachment
from app.schemas.complaint import ComplaintCreate, AttachmentCreate

class ComplaintService:
    
    @staticmethod
    def generate_tracking_code() -> str:
        letters = string.ascii_uppercase
        digits = ''.join(random.choices(string.digits, k=4))
        random_letters = ''.join(random.choices(letters, k=3))
        return f"CMP-{random_letters}-{digits}"

    @staticmethod
    def create_complaint(db: Session, complaint_in: ComplaintCreate) -> Complaint:
        tracking_code = ComplaintService.generate_tracking_code()
        
        # التأكد من أن كود التتبع فريد
        while db.query(Complaint).filter(Complaint.tracking_code == tracking_code).first():
            tracking_code = ComplaintService.generate_tracking_code()

        db_complaint = Complaint(
            tracking_code=tracking_code,
            citizen_id=complaint_in.citizen_id,
            directorate_id=complaint_in.directorate_id,
            title=complaint_in.title,
            details=complaint_in.details,
            category=complaint_in.category,
            priority=complaint_in.priority
        )
        
        db.add(db_complaint)
        db.commit()
        db.refresh(db_complaint)
        return db_complaint

    @staticmethod
    def add_attachment(db: Session, attachment_in: AttachmentCreate) -> Attachment:
        db_attachment = Attachment(
            file_path=attachment_in.file_path,
            file_type=attachment_in.file_type,
            attachable_type=attachment_in.attachable_type,
            attachable_id=attachment_in.attachable_id
        )
        db.add(db_attachment)
        db.commit()
        db.refresh(db_attachment)
        return db_attachment