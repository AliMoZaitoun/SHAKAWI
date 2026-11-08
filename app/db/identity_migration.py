"""Idempotent, additive identity backfill. Never merge people by guessed data."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from sqlalchemy import inspect, text


def backup_legacy_sqlite(engine):
    inspector = inspect(engine)
    if engine.dialect.name != "sqlite" or engine.url.database in (None, "", ":memory:"):
        return
    if "user_id" in {c["name"] for c in inspector.get_columns("employees")}:
        return
    directory = Path("generated-artifacts/db-backups")
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = directory / f"before-identity-{stamp}.sqlite"
    raw = engine.raw_connection()
    try:
        with sqlite3.connect(destination) as target:
            raw.driver_connection.backup(target)
    finally:
        raw.close()


def backfill_identity(engine):
    tables = set(inspect(engine).get_table_names())
    if not {"users", "directorates", "citizens", "employees"}.issubset(tables):
        return
    with engine.begin() as conn:
        existing = set(conn.execute(text("SELECT id FROM directorates")).scalars())
        required = {1, 2}
        for table in ("employees", "complaints"):
            required.update(conn.execute(text(
                f"SELECT DISTINCT directorate_id FROM {table} WHERE directorate_id IS NOT NULL"
            )).scalars())
        names = {1: "المحافظة", 2: "الخدمات"}
        for identifier in sorted(required - existing):
            if identifier <= 0:
                raise RuntimeError("Legacy directorate IDs must be positive; migration stopped without deleting records")
            conn.execute(text(
                "INSERT INTO directorates (id, name, description, location, is_active) "
                "VALUES (:id, :name, '', '', TRUE)"
            ), {"id": identifier, "name": names.get(identifier, f"مديرية مستوردة {identifier}")})
        from app.models.access import User
        for table, kind in (("citizens", "citizen"), ("employees", "employee")):
            rows = conn.execute(text(f"SELECT * FROM {table} WHERE user_id IS NULL")).mappings()
            for row in list(rows):
                values = {"user_type": kind, "is_active": True}
                if kind == "citizen":
                    values.update(first_name=row["first_name"], last_name=row["last_name"],
                                  phone=row["phone"], needs_profile_completion=False)
                else:
                    values.update(first_name=row["full_name"], last_name=None, phone=None,
                                  username=row["username"], hashed_password=row["hashed_password"],
                                  needs_profile_completion=True)
                result = conn.execute(User.__table__.insert().values(**values))
                conn.execute(text(f"UPDATE {table} SET user_id = :uid WHERE id = :id"),
                             {"uid": result.inserted_primary_key[0], "id": row["id"]})
            conn.execute(text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_user_id ON {table}(user_id)"
            ))
