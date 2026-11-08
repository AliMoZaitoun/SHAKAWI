"""Transition adapter: keep old API contracts without two writable identities."""
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.access import User
from app.models.user import Citizen, Employee


@event.listens_for(Session, "before_flush")
def sync_identity(session, flush_context, instances):
    """Legacy writes and new account writes are synchronized in one transaction.

    Existing columns stay during the compatibility window. Credentials are
    copied unchanged; a migration never resets or re-hashes passwords.
    """
    pending = list(session.new) + list(session.dirty)
    for profile in pending:
        if not isinstance(profile, (Citizen, Employee)) or profile in session.deleted:
            continue
        if profile.user is None:
            if isinstance(profile, Citizen):
                profile.user = User(
                    first_name=profile.first_name, last_name=profile.last_name,
                    phone=profile.phone, user_type="citizen",
                )
            else:
                # A legacy full name does not tell us which part is a surname.
                profile.user = User(
                    first_name=profile.full_name, user_type="employee",
                    username=profile.username, hashed_password=profile.hashed_password,
                    needs_profile_completion=True,
                )
        # Hybrid setters write to User immediately. Raw legacy column changes
        # never overwrite the canonical account during a later flush.
    for account in list(session.new) + list(session.dirty):
        if not isinstance(account, User) or account in session.deleted:
            continue
        if account.citizen:
            for field in ("first_name", "last_name", "phone"):
                setattr(account.citizen, "_legacy_" + field, getattr(account, field))
        if account.employee:
            employee = account.employee
            employee._legacy_username = account.username
            employee._legacy_hashed_password = account.hashed_password
            if account.last_name:
                employee._legacy_full_name = f"{account.first_name} {account.last_name}"
