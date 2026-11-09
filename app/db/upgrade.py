"""Single versioned schema entry point for startup and local CLI."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[2]
PRESERVED_TABLES = {
    "citizens", "employees", "complaints", "attachments", "complaint_notes",
    "evidence_requests", "evidence_replies", "evidence_files",
    "citizen_recovery_keys", "citizen_ownership_challenges", "directorates",
    "public_complaint_reports", "public_complaint_reviews",
}


def upgrade_database(engine):
    tables = inspect(engine).get_table_names()
    current = None
    if "alembic_version" in tables:
        with engine.connect() as conn:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    config = Config(str(ROOT / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if current != head and any(name in tables for name in ("users", "citizens", "complaints")):
        from app.db.backup import create_backup
        create_backup(engine)
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite" and not conn.connection.driver_connection.in_transaction:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        config.attributes["connection"] = conn
        before = {name: conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar()
                  for name in PRESERVED_TABLES.intersection(tables)}
        command.upgrade(config, "head")
        for name, count in before.items():
            if conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar() != count:
                raise RuntimeError(f"Preserved record count changed in {name}; upgrade rolled back")
        if engine.dialect.name == "sqlite":
            if conn.exec_driver_sql("PRAGMA foreign_key_check").first():
                raise RuntimeError("Foreign key validation failed; no destructive repair attempted")


if __name__ == "__main__":
    from app.db.session import engine
    upgrade_database(engine)
    print("Database upgraded to the current revision.")
