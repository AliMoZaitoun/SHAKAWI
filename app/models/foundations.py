"""Extensible translations, private file catalog and durable business history."""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.sql import func
from app.db.base import Base


class Language(Base):
    __tablename__ = "languages"
    code = Column(String(35), primary_key=True)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    direction = Column(String(3), nullable=False, default="ltr", server_default="ltr")
    __table_args__ = (CheckConstraint("direction IN ('rtl', 'ltr')"),)


class UserLanguage(Base):
    __tablename__ = "user_languages"
    user_id = Column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    language_code = Column(ForeignKey("languages.code", ondelete="RESTRICT"), nullable=False)


class RoleTranslation(Base):
    __tablename__ = "role_translations"
    role_id = Column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    language_code = Column(ForeignKey("languages.code", ondelete="RESTRICT"), primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="")


class PermissionTranslation(Base):
    __tablename__ = "permission_translations"
    permission_code = Column(ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True)
    language_code = Column(ForeignKey("languages.code", ondelete="RESTRICT"), primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="")


class DirectorateTranslation(Base):
    __tablename__ = "directorate_translations"
    directorate_id = Column(ForeignKey("directorates.id", ondelete="CASCADE"), primary_key=True)
    language_code = Column(ForeignKey("languages.code", ondelete="RESTRICT"), primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="")
    location = Column(String(500), nullable=False, default="")


class StoredFile(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    storage_disk = Column(String(30), nullable=False, default="local", server_default="local")
    storage_key = Column(String(500), nullable=False, unique=True)
    original_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=True)
    checksum = Column(String(64), nullable=True)
    uploaded_by_user_id = Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ComplaintFile(Base):
    __tablename__ = "complaint_files"
    file_id = Column(ForeignKey("files.id", ondelete="RESTRICT"), primary_key=True)
    complaint_id = Column(ForeignKey("complaints.id", ondelete="RESTRICT"), primary_key=True, index=True)
    legacy_attachment_id = Column(ForeignKey("attachments.id", ondelete="RESTRICT"), unique=True, nullable=True)


class CitizenFile(Base):
    __tablename__ = "citizen_files"
    file_id = Column(ForeignKey("files.id", ondelete="RESTRICT"), primary_key=True)
    citizen_id = Column(ForeignKey("citizens.id", ondelete="RESTRICT"), primary_key=True)
    purpose = Column(String(30), nullable=False, default="identity")
    is_current = Column(Boolean, nullable=False, default=True)


class EvidenceReplyFile(Base):
    __tablename__ = "evidence_reply_files"
    file_id = Column(ForeignKey("files.id", ondelete="RESTRICT"), primary_key=True)
    reply_id = Column(ForeignKey("evidence_replies.id", ondelete="RESTRICT"), primary_key=True, index=True)
    legacy_evidence_file_id = Column(ForeignKey("evidence_files.id", ondelete="RESTRICT"), unique=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    actor_user_id = Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(60), nullable=False, index=True)
    entity_id = Column(String(80), nullable=False)
    changes = Column(JSON, nullable=False, default=dict)
    source = Column(String(20), nullable=False, default="system")
    request_id = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class ComplaintHistory(Base):
    __tablename__ = "complaint_history"
    id = Column(Integer, primary_key=True)
    complaint_id = Column(ForeignKey("complaints.id", ondelete="RESTRICT"), nullable=False, index=True)
    actor_user_id = Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    event = Column(String(30), nullable=False)
    old_status = Column(String(30))
    new_status = Column(String(30), nullable=False)
    old_directorate_id = Column(ForeignKey("directorates.id", ondelete="RESTRICT"))
    new_directorate_id = Column(ForeignKey("directorates.id", ondelete="RESTRICT"), nullable=False)
    old_progress = Column(Integer)
    new_progress = Column(Integer, nullable=False)
    reason = Column(String(1000), nullable=False, default="")
    source = Column(String(20), nullable=False)
    request_id = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
