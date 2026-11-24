import secrets
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.complaint import Complaint, ComplaintType, Attachment
from app.schemas.complaint import ComplaintCreate, AttachmentCreate

class ComplaintService:
    
    @staticmethod
    def generate_tracking_code() -> str:
        return f"CMP-{secrets.token_hex(8).upper()}"

    @staticmethod
    def create_complaint(db: Session, complaint_in: ComplaintCreate) -> Complaint:
        tracking_code = ComplaintService.generate_tracking_code()
        
        # التأكد من أن كود التتبع فريد
        while db.query(Complaint).filter(Complaint.tracking_code == tracking_code).first():
            tracking_code = ComplaintService.generate_tracking_code()

        complaint_type = None
        if complaint_in.complaint_type_id is not None:
            complaint_type = db.get(ComplaintType, complaint_in.complaint_type_id)
            if not complaint_type or not complaint_type.is_active:
                raise HTTPException(422, "نوع الشكوى غير موجود أو غير مفعّل")
            # Keep the Arabic label as a stable compatibility snapshot for old
            # reports. New clients use complaint_type_id and localized metadata.
            category = complaint_type.name
            sla_duration_minutes = complaint_type.sla_duration_minutes
        else:
            category = complaint_in.category
            sla_duration_minutes = None

        db_complaint = Complaint(
            tracking_code=tracking_code,
            citizen_id=complaint_in.citizen_id,
            directorate_id=complaint_in.directorate_id,
            title=complaint_in.title,
            details=complaint_in.details,
            category=category,
            complaint_type_id=complaint_type.id if complaint_type else None,
            sla_duration_minutes=sla_duration_minutes,
            priority=complaint_in.priority,
            is_public=complaint_in.is_public,
            latitude=complaint_in.latitude,
            longitude=complaint_in.longitude
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