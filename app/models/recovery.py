"""Only digests of bearer credentials are stored, never their plaintext."""
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, ForeignKey
from app.db.base import Base


class RecoveryKey(Base):
    __tablename__ = "citizen_recovery_keys"
    citizen_id = Column(Integer, ForeignKey("citizens.id"), primary_key=True)
    digest = Column(String(64), unique=True, nullable=False)


class OwnershipChallenge(Base):
    __tablename__ = "citizen_ownership_challenges"
    digest = Column(String(64), primary_key=True)
    citizen_id = Column(Integer, ForeignKey("citizens.id"), nullable=False)
    purpose = Column(String(16), nullable=False)
    browser_digest = Column(String(64), nullable=True)
    expected_telegram_id = Column(BigInteger, nullable=True)
    expires_at = Column(BigInteger, nullable=False)
    approved = Column(Boolean, default=False, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
