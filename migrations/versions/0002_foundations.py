"""Languages, private catalog and transactional history; no legacy column drops."""
from alembic import op
from sqlalchemy.orm import Session

revision = "0002_foundations"
down_revision = "0001_legacy"
branch_labels = depends_on = None


def upgrade():
    from app.services.translations import seed_translations
    from app.services.file_catalog import backfill_files
    from app.db.foundations_backfill import backfill_history
    connection = op.get_bind()
    from app.db.schema_snapshot import apply_snapshot
    apply_snapshot(connection, "foundations_schema.sql")
    with Session(bind=connection) as db:
        db.info["disable_audit"] = True
        seed_translations(db)
        backfill_files(db)
        backfill_history(db)
        db.flush()


def downgrade():
    raise RuntimeError("Destructive downgrade disabled. Restore the verified backup; no data is dropped automatically.")
