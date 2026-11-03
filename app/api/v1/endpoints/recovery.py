"""Explicit owner-authorized recovery and Telegram binding.

Public challenge handles are not credentials: browser recovery additionally
requires a private, session-bound nonce and approval by the original Telegram.
"""
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import (check_recovery_rate, credential_digest, grant_citizen,
                               owns_citizen, require_bot)
from app.db.session import get_db
from app.models.recovery import OwnershipChallenge, RecoveryKey
from app.models.user import Citizen
from app.schemas.user import CitizenResponse

router = APIRouter()


class Credential(BaseModel):
    token: str = Field(min_length=32, max_length=100)


class TelegramProof(Credential):
    telegram_id: int = Field(gt=0)


class RecoveryStart(BaseModel):
    telegram_id: int = Field(gt=0)
    consent: bool


def owner(request, db):
    citizen_id = request.session.get("citizen_id")
    citizen = db.get(Citizen, citizen_id) if citizen_id else None
    if not citizen or not owns_citizen(request, citizen.id):
        raise HTTPException(403, "يلزم إثبات ملكية السجل أولًا")
    return citizen


def invalid():
    return HTTPException(400, "الطلب غير صالح أو انتهت صلاحيته أو استُخدم سابقًا")


def live(db, token, purpose):
    return db.query(OwnershipChallenge).filter(
        OwnershipChallenge.digest == credential_digest(token),
        OwnershipChallenge.purpose == purpose,
        OwnershipChallenge.expires_at > int(time.time()),
        OwnershipChallenge.consumed.is_(False),
    )


def challenge(db, citizen, purpose, browser=None):
    token = secrets.token_urlsafe(32)
    row = OwnershipChallenge(
        digest=credential_digest(token), citizen_id=citizen.id, purpose=purpose,
        expected_telegram_id=citizen.telegram_id,
        browser_digest=credential_digest(browser) if browser else None,
        expires_at=int(time.time()) + 600,
    )
    # A new request from an authenticated owner invalidates older link grants.
    if purpose == "link":
        db.query(OwnershipChallenge).filter_by(citizen_id=citizen.id, purpose="link").update(
            {"consumed": True})
    db.add(row)
    db.commit()
    return token


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    citizen = owner(request, db)
    return {"citizen": CitizenResponse.model_validate(citizen),
            "has_recovery_key": db.get(RecoveryKey, citizen.id) is not None}


@router.post("/key")
def issue_key(request: Request, db: Session = Depends(get_db)):
    check_recovery_rate(request)
    citizen = owner(request, db)
    token = secrets.token_urlsafe(32)
    db.merge(RecoveryKey(citizen_id=citizen.id, digest=credential_digest(token)))
    db.commit()
    return {"key": token}


@router.post("/key/restore", response_model=CitizenResponse)
def restore_key(data: Credential, request: Request, db: Session = Depends(get_db)):
    check_recovery_rate(request)
    row = db.query(RecoveryKey).filter_by(digest=credential_digest(data.token)).first()
    if not row:
        raise invalid()
    citizen = db.get(Citizen, row.citizen_id)
    # Conditional deletion is atomic: concurrent redemptions cannot both win.
    count = db.query(RecoveryKey).filter_by(citizen_id=row.citizen_id, digest=row.digest).delete(
        synchronize_session=False)
    db.commit()
    if count != 1:
        raise invalid()
    grant_citizen(request, citizen.id)
    return citizen


@router.post("/telegram/start")
def start(data: RecoveryStart, request: Request, db: Session = Depends(get_db)):
    check_recovery_rate(request)
    if not data.consent:
        raise HTTPException(400, "الموافقة على وسيلة الاستعادة مطلوبة")
    browser = secrets.token_urlsafe(32)
    request.session["recovery_browser"] = browser
    citizen = db.query(Citizen).filter_by(telegram_id=data.telegram_id).first()
    # Same response shape for unknown accounts; do not expose existence.
    token = challenge(db, citizen, "recover", browser) if citizen else secrets.token_urlsafe(32)
    return {"token": token, "expires_in": 600}


@router.post("/telegram/approve", dependencies=[Depends(require_bot)])
def approve(data: TelegramProof, request: Request, db: Session = Depends(get_db)):
    check_recovery_rate(request)
    row = live(db, data.token, "recover").first()
    if not row or row.expected_telegram_id != data.telegram_id:
        raise invalid()
    citizen = db.get(Citizen, row.citizen_id)
    if citizen.telegram_id != data.telegram_id:
        raise invalid()
    row.approved = True
    db.commit()
    return {"message": "تمت الموافقة. أكمل الاستعادة في المتصفح الذي بدأ الطلب."}


@router.post("/telegram/finish", response_model=CitizenResponse)
def finish(data: Credential, request: Request, db: Session = Depends(get_db)):
    check_recovery_rate(request)
    query = live(db, data.token, "recover").filter(
        OwnershipChallenge.approved.is_(True),
        OwnershipChallenge.browser_digest == credential_digest(request.session.get("recovery_browser", "")),
        OwnershipChallenge.expected_telegram_id == db.query(Citizen.telegram_id).filter(
            Citizen.id == OwnershipChallenge.citizen_id).scalar_subquery())
    row = query.first()
    if not row:
        raise invalid()
    citizen = db.get(Citizen, row.citizen_id)
    if citizen.telegram_id != row.expected_telegram_id:
        raise invalid()
    if query.update({"consumed": True}, synchronize_session=False) != 1:
        db.rollback()
        raise invalid()
    db.commit()
    request.session.pop("recovery_browser", None)
    grant_citizen(request, citizen.id)
    return citizen


@router.post("/telegram/link")
def link(request: Request, db: Session = Depends(get_db)):
    check_recovery_rate(request)
    citizen = owner(request, db)
    return {"token": challenge(db, citizen, "link"), "expires_in": 600}


@router.post("/telegram/confirm-link", dependencies=[Depends(require_bot)],
             response_model=CitizenResponse)
def confirm_link(data: TelegramProof, request: Request, db: Session = Depends(get_db)):
    check_recovery_rate(request)
    query = live(db, data.token, "link")
    row = query.first()
    if not row:
        raise invalid()
    # Consume the grant and conditionally change the original binding within
    # one transaction, including unique Telegram constraints.
    if query.update({"consumed": True}, synchronize_session=False) != 1:
        db.rollback()
        raise invalid()
    from sqlalchemy.exc import IntegrityError
    try:
        changed = db.query(Citizen).filter(
            Citizen.id == row.citizen_id,
            Citizen.telegram_id == row.expected_telegram_id,
        ).update({"telegram_id": data.telegram_id}, synchronize_session=False)
        if changed != 1:
            db.rollback()
            raise invalid()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "حساب تيليغرام مرتبط بسجل آخر")
    db.expire_all()
    return db.get(Citizen, row.citizen_id)
