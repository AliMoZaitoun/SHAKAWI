"""Extensible translations, private file catalog and durable business history."""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.sql import func
from app.db.base import Base
from app.models.complaint import ComplaintType


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


class ComplaintTypeTranslation(Base):
    __tablename__ = "complaint_type_translations"
    complaint_type_id = Column(ForeignKey("complaint_types.id", ondelete="CASCADE"), primary_key=True)
    language_code = Column(ForeignKey("languages.code", ondelete="RESTRICT"), primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="")


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
    purged_at = Column(DateTime(timezone=True), nullable=True)


class FilePolicy(Base):
    __tablename__ = "file_policies"
    id = Column(Integer, primary_key=True)
    mime_limits = Column(JSON, nullable=False)
    retention_enabled = Column(Boolean, nullable=False, default=False, server_default="0")
    retention_days = Column(Integer, nullable=False, default=30, server_default="30")
    retention_scope = Column(JSON, nullable=False)
    retention_policy_version = Column(Integer, nullable=False, default=1, server_default="1")
    retention_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    retention_review_fingerprint = Column(String(64), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)


class BrandSettings(Base):
    __tablename__ = "brand_settings"
    id = Column(Integer, primary_key=True)
    hero_art_style = Column(
        String(24),
        nullable=False,
        default="flowing_lines",
        server_default="flowing_lines",
    )
    brand_dark = Column(String(7), nullable=False, default="#3b4b32")
    brand_primary = Column(String(7), nullable=False, default="#4a5d3f")
    brand_light = Column(String(7), nullable=False, default="#657b57")
    brand_accent = Column(String(7), nullable=False, default="#b88d4b")
    brand_gold = Column(String(7), nullable=False, default="#d4a860")
    brand_bg = Column(String(7), nullable=False, default="#f7f8f4")
    brand_card = Column(String(7), nullable=False, default="#ffffff")
    sidebar_item_bg = Column(String(7), nullable=False, default="#edf1e8")
    logo_path = Column(String(500), nullable=True)
    logo_version = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)


class PrintTemplateSettings(Base):
    __tablename__ = "print_template_settings"
    id = Column(Integer, primary_key=True)
    titles = Column(JSON, nullable=False)
    default_sections = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_user_id = Column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)


class RetentionPreview(Base):
    __tablename__ = "retention_previews"
    token_hash = Column(String(64), primary_key=True)
    policy_version = Column(Integer, nullable=False)
    cutoff_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    candidate_fingerprint = Column(String(64), nullable=False)
    file_count = Column(Integer, nullable=False)
    bytes_total = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RetentionRun(Base):
    __tablename__ = "retention_runs"
    id = Column(Integer, primary_key=True)
    run_key = Column(String(100), nullable=False, unique=True)
    policy_version = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)
    files_scanned = Column(Integer, nullable=False, default=0)
    files_purged = Column(Integer, nullable=False, default=0)
    bytes_purged = Column(Integer, nullable=False, default=0)
    failures = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)


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
