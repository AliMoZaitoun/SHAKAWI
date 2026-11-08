"""Adopt the existing schema additively without stamping an unverified database."""
from alembic import op

revision = "0001_legacy"
down_revision = None
branch_labels = depends_on = None


def upgrade():
    from app.db.migrations import migrate_connection
    connection = op.get_bind()
    from app.db.schema_snapshot import apply_snapshot
    apply_snapshot(connection, "legacy_schema.sql")
    migrate_connection(connection)
    apply_snapshot(connection, "legacy_indexes.sql")


def downgrade():
    raise RuntimeError("Destructive downgrade disabled. Restore the pre-upgrade database and uploads backup.")
