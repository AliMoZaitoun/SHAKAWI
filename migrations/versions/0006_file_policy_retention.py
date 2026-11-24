"""Central file limits and explicitly reviewed attachment retention."""
from alembic import op
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    inspect,
    text,
)

revision = "0006_file_policy_retention"
down_revision = "0005_complaint_types"
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    tables = set(inspect(connection).get_table_names())

    if "file_policies" not in tables:
        op.create_table(
            "file_policies",
            Column("id", Integer(), primary_key=True),
            Column("mime_limits", JSON(), nullable=False, server_default=text("'{}'")),
            Column("retention_enabled", Boolean(), nullable=False, server_default=text("0")),
            Column("retention_days", Integer(), nullable=False, server_default=text("30")),
            Column("retention_scope", JSON(), nullable=False, server_default=text("'[]'")),
            Column("retention_policy_version", Integer(), nullable=False, server_default=text("1")),
            Column("retention_reviewed_at", DateTime(timezone=True)),
            Column("retention_review_fingerprint", String(length=64)),
            Column("updated_at", DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")),
            Column("updated_by_user_id", Integer(), ForeignKey("users.id", ondelete="RESTRICT")),
        )
    if "retention_previews" not in tables:
        op.create_table(
            "retention_previews",
            Column("token_hash", String(length=64), primary_key=True),
            Column("policy_version", Integer(), nullable=False),
            Column("cutoff_at", DateTime(timezone=True), nullable=False),
            Column("expires_at", DateTime(timezone=True), nullable=False),
            Column("candidate_fingerprint", String(length=64), nullable=False),
            Column("file_count", Integer(), nullable=False),
            Column("bytes_total", Integer(), nullable=False),
            Column("created_at", DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")),
        )
    if "retention_runs" not in tables:
        op.create_table(
            "retention_runs",
            Column("id", Integer(), primary_key=True),
            Column("run_key", String(length=100), nullable=False, unique=True),
            Column("policy_version", Integer(), nullable=False),
            Column("status", String(length=20), nullable=False),
            Column("files_scanned", Integer(), nullable=False, server_default=text("0")),
            Column("files_purged", Integer(), nullable=False, server_default=text("0")),
            Column("bytes_purged", Integer(), nullable=False, server_default=text("0")),
            Column("failures", Integer(), nullable=False, server_default=text("0")),
            Column("started_at", DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")),
            Column("finished_at", DateTime(timezone=True)),
        )
    columns = {column["name"] for column in inspect(connection).get_columns("files")}
    if "purged_at" not in columns:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("ALTER TABLE files ADD COLUMN purged_at DATETIME")
        else:
            op.add_column("files", Column("purged_at", DateTime(timezone=True), nullable=True))

    columns = {column["name"] for column in inspect(connection).get_columns("complaints")}
    if "resolved_at" not in columns:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("ALTER TABLE complaints ADD COLUMN resolved_at DATETIME")
        else:
            op.add_column(
                "complaints", Column("resolved_at", DateTime(timezone=True), nullable=True)
            )
    # For legacy resolved records, use a known last-updated timestamp only.
    # Rows without one are excluded from automatic retention until resolved again.
    if {"status", "updated_at", "resolved_at"}.issubset(
        {column["name"] for column in inspect(connection).get_columns("complaints")}
    ):
        connection.execute(text(
            "UPDATE complaints SET resolved_at = updated_at "
            "WHERE status = 'RESOLVED' AND updated_at IS NOT NULL AND resolved_at IS NULL"
        ))


def downgrade():
    raise RuntimeError(
        "Destructive downgrade disabled because file content may already have been purged. "
        "Restore a verified database backup instead."
    )
