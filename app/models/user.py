from enum import Enum
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
from app.models.access import User
from app.models.identity_fields import identity_field, account_full_name

class UserRole(str, Enum):
    CITIZEN = "citizen"
    EMPLOYEE = "employee"
    GOVERNOR = "governor"

class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    _legacy_first_name = Column("first_name", String(50), nullable=False)
    _legacy_last_name = Column("last_name", String(50), nullable=False)
    _legacy_phone = Column("phone", String(20), unique=True, nullable=False, index=True)
    first_name = identity_field("first_name", "_legacy_first_name")
    last_name = identity_field("last_name", "_legacy_last_name")
    phone = identity_field("phone", "_legacy_phone")
    national_id = Column(String(20), unique=True, nullable=False, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    identity_card_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    complaints = relationship("Complaint", back_populates="citizen")
    user = relationship("User", back_populates="citizen")

class Employee(Base):
    __tablename__ = "employees"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    rbac_initialized = Column(Boolean, nullable=False, default=False, server_default="0")
    _legacy_full_name = Column("full_name", String(100), nullable=False)
    full_name = account_full_name()
    _legacy_username = Column("username", String(50), unique=True, nullable=False, index=True)
    _legacy_hashed_password = Column("hashed_password", String(255), nullable=False)
    username = identity_field("username", "_legacy_username")
    hashed_password = identity_field("hashed_password", "_legacy_hashed_password")
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    is_demo = Column(Boolean, nullable=False, default=False, server_default="0")
    password_version = Column(Integer, nullable=False, default=1, server_default="1")
    directorate_id = Column(BigInteger, ForeignKey("directorates.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    notes = relationship("ComplaintNote", back_populates="author")
    user = relationship("User", back_populates="employee")
    directorate = relationship("Directorate")
    role_assignments = relationship("RoleAssignment", back_populates="employee", lazy="selectin")