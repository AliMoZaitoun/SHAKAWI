from enum import Enum
from sqlalchemy import Column, BigInteger, Integer, String, Float, Text, DateTime, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class PriorityEnum(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"

class StatusEnum(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)    
    tracking_code = Column(String(30), unique=True, nullable=False, index=True)
    citizen_id = Column(BigInteger, ForeignKey("citizens.id"), nullable=False)
    directorate_id = Column(BigInteger, nullable=False, index=True)
    
    title = Column(String(150), nullable=False)
    details = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    is_public = Column(Boolean, nullable=False, default=False, server_default="0", index=True)
    
    priority = Column(SQLEnum(PriorityEnum), default=PriorityEnum.MEDIUM, nullable=False)
    status = Column(SQLEnum(StatusEnum), default=StatusEnum.PENDING, nullable=False)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    progress = Column(Integer, nullable=False, default=0, server_default="0")
    resolution_report = Column(Text, nullable=False, default="", server_default="")

    citizen = relationship("Citizen", back_populates="complaints")
    notes = relationship("ComplaintNote", back_populates="complaint", cascade="all, delete-orphan")

class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    file_path = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # image, pdf, audio
    attachable_type = Column(String(50), nullable=False, index=True)  # 'complaints', 'citizens', etc.
    attachable_id = Column(BigInteger, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ComplaintNote(Base):
    __tablename__ = "complaint_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(BigInteger, ForeignKey("complaints.id"), nullable=False)
    author_id = Column(BigInteger, ForeignKey("employees.id"), nullable=False)
    note = Column(Text, nullable=False)
    is_internal = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    complaint = relationship("Complaint", back_populates="notes")
    author = relationship("Employee", back_populates="notes")
    notification_status = Column(String(30), nullable=False, default="not_requested", server_default="not_requested")
    notification_error = Column(Text, nullable=True)