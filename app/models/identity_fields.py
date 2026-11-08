"""Canonical user-backed attributes with legacy column mirrors, not two sources."""
from sqlalchemy import select, func
from sqlalchemy.ext.hybrid import hybrid_property
from app.models.access import User


def identity_field(name, legacy):
    @hybrid_property
    def field(self):
        account = self.user
        value = getattr(account, name) if account is not None else None
        return value if value is not None else getattr(self, legacy)

    @field.inplace.setter
    def set_field(self, value):
        setattr(self, legacy, value)
        if self.user is not None:
            setattr(self.user, name, value)

    @field.inplace.expression
    @classmethod
    def expression(cls):
        value = select(getattr(User, name)).where(User.id == cls.user_id).correlate(cls).scalar_subquery()
        return func.coalesce(value, getattr(cls, legacy))

    return field


def account_full_name():
    @hybrid_property
    def field(self):
        account = self.user
        if account is not None and account.first_name:
            return " ".join(value for value in (account.first_name, account.last_name) if value)
        return self._legacy_full_name

    @field.inplace.setter
    def set_field(self, value):
        # A legacy full name is never split into guessed personal data.
        self._legacy_full_name = value

    @field.inplace.expression
    @classmethod
    def expression(cls):
        value = select(func.trim(User.first_name + " " + func.coalesce(User.last_name, ""))).where(
            User.id == cls.user_id).correlate(cls).scalar_subquery()
        return func.coalesce(value, cls._legacy_full_name)

    return field
