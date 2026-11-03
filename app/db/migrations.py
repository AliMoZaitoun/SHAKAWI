"""Small, additive migration for the imported SQLite database; no table rebuilds."""
from sqlalchemy import inspect, text


def migrate(engine):
    additions = {
        "complaints": {
            "progress": "INTEGER NOT NULL DEFAULT 0",
            "resolution_report": "TEXT NOT NULL DEFAULT ''",
        },
        "complaint_notes": {
            "notification_status": "VARCHAR(30) NOT NULL DEFAULT 'not_requested'",
            "notification_error": "TEXT",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = {col["name"] for col in inspector.get_columns(table)}
            for name, declaration in columns.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}'))
