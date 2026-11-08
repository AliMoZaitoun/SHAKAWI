from enum import Enum
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
from app.models.access import User

class UserRole(str, Enum):
    CITIZEN = "citizen"
    EMPLOYEE = "employee"
    GOVERNOR = "governor"

class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
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
    full_name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    is_demo = Column(Boolean, nullable=False, default=False, server_default="0")
    password_version = Column(Integer, nullable=False, default=1, server_default="1")
    directorate_id = Column(BigInteger, ForeignKey("directorates.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    notes = relationship("ComplaintNote", back_populates="author")
    user = relationship("User", back_populates="employee")
    directorate = relationship("Directorate")
    role_assignments = relationship("RoleAssignment", back_populates="employee", lazy="selectin")