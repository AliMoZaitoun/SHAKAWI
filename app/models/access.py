"""Identity and scoped RBAC tables; independent of the presentation layer."""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String,
    Table, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True, unique=True)
    email = Column(String(254), nullable=True, unique=True)
    username = Column(String(50), nullable=True, unique=True)
    hashed_password = Column(String(255), nullable=True)
    user_type = Column(String(20), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    needs_profile_completion = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (CheckConstraint("user_type IN ('citizen', 'employee')"),)

    citizen = relationship("Citizen", back_populates="user", uselist=False)
    employee = relationship("Employee", back_populates="user", uselist=False)


class Directorate(Base):
    __tablename__ = "directorates"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="", server_default="")
    location = Column(String(500), nullable=False, default="", server_default="")
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


role_permissions = Table(
    "role_permissions", Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_code", ForeignKey("permissions.code", ondelete="RESTRICT"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"
    code = Column(String(80), primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="", server_default="")


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    code = Column(String(60), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=False, default="", server_default="")
    is_system = Column(Boolean, nullable=False, default=False, server_default="0")
    permissions = relationship("Permission", secondary=role_permissions, lazy="selectin")
    assignments = relationship("RoleAssignment", back_populates="role")


class RoleAssignment(Base):
    __tablename__ = "employee_role_assignments"
    id = Column(Integer, primary_key=True)
    employee_id = Column(ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    role_id = Column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, index=True)
    scope_type = Column(String(20), nullable=False)
    directorate_id = Column(ForeignKey("directorates.id", ondelete="RESTRICT"), nullable=True)
    # NULLs are distinct in SQLite UNIQUE constraints. A checked, non-null key
    # also prevents duplicate global grants and has identical semantics on PG.
    scope_key = Column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'global' AND directorate_id IS NULL AND scope_key = 0) OR "
            "(scope_type = 'directorate' AND directorate_id IS NOT NULL "
            "AND directorate_id > 0 AND scope_key = directorate_id)"
        ),
        UniqueConstraint("employee_id", "role_id", "scope_key"),
    )
    role = relationship("Role", back_populates="assignments")
    employee = relationship("Employee", back_populates="role_assignments")
    directorate = relationship("Directorate")


class AccessAudit(Base):
    __tablename__ = "access_audit"
    id = Column(Integer, primary_key=True)
    actor_id = Column(ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False)
    action = Column(String(80), nullable=False)
    target_type = Column(String(40), nullable=False)
    target_id = Column(String(80), nullable=False)
    # Metadata only: never credentials, personal documents or password hashes.
    details = Column(Text, nullable=False, default="", server_default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
