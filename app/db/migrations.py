"""Small, additive migration for the imported SQLite database; no table rebuilds."""
from sqlalchemy import inspect, text


def migrate(engine):
    from app.db.identity_migration import backup_legacy_sqlite, backfill_identity
    backup_legacy_sqlite(engine)
    with engine.begin() as conn:
        migrate_connection(conn)


def migrate_connection(conn):
    from app.db.identity_migration import backfill_identity_connection
    additions = {
        "complaints": {
            "progress": "INTEGER NOT NULL DEFAULT 0",
            "resolution_report": "TEXT NOT NULL DEFAULT ''",
            "is_public": "BOOLEAN NOT NULL DEFAULT FALSE",
            "public_text_hidden": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
        "complaint_notes": {
            "audience": "VARCHAR(20) NOT NULL DEFAULT 'private'",
            "notification_status": "VARCHAR(30) NOT NULL DEFAULT 'not_requested'",
            "notification_error": "TEXT",
        },
        "employees": {
            "user_id": "INTEGER REFERENCES users(id)",
            "rbac_initialized": "BOOLEAN NOT NULL DEFAULT FALSE",
            "is_demo": "BOOLEAN NOT NULL DEFAULT FALSE",
            "password_version": "INTEGER NOT NULL DEFAULT 1",
        },
        "citizens": {
            "user_id": "INTEGER REFERENCES users(id)",
        },
    }
    inspector = inspect(conn)
    for table, columns in additions.items():
        if table not in inspector.get_table_names():
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        for name, declaration in columns.items():
            if name not in existing:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}'))
    # Normalize inconsistent legacy values without inventing completion dates.
    if "complaints" in inspector.get_table_names():
        conn.execute(text("UPDATE complaints SET progress = 100 WHERE status = 'RESOLVED' AND progress <> 100"))
        conn.execute(text("UPDATE complaints SET progress = 0 WHERE status <> 'RESOLVED' AND progress >= 100"))
    if "complaint_notes" in inspector.get_table_names():
        if "is_internal" in {c["name"] for c in inspector.get_columns("complaint_notes")}:
            conn.execute(text("UPDATE complaint_notes SET audience = 'internal' WHERE is_internal = 1"))
    backfill_identity_connection(conn)
