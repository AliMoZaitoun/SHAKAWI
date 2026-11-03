from enum import Enum
from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class UserRole(str, Enum):
    CITIZEN = "citizen"
    EMPLOYEE = "employee"
    GOVERNOR = "governor"

class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    national_id = Column(String(20), unique=True, nullable=False, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    identity_card_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    complaints = relationship("Complaint", back_populates="citizen")

class Employee(Base):
    __tablename__ = "employees"

    id = Column(BigInteger, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.EMPLOYEE, nullable=False)
    is_demo = Column(Boolean, nullable=False, default=False, server_default="0")
    password_version = Column(Integer, nullable=False, default=1, server_default="1")
    directorate_id = Column(BigInteger, nullable=True)  # رقم المديرية التابع لها
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    notes = relationship("ComplaintNote", back_populates="author")