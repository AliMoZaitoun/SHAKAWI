"""Add nullable parent links to directorates without changing existing rows."""
from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa

revision = "0003_directorate_hierarchy"
down_revision = "0002_foundations"
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("directorates")}
    if "parent_id" not in columns:
        op.add_column(
            "directorates",
            sa.Column(
                "parent_id",
                sa.Integer(),
                sa.ForeignKey("directorates.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )
    indexes = {index["name"] for index in inspector.get_indexes("directorates")}
    if "ix_directorates_parent_id" not in indexes:
        op.create_index("ix_directorates_parent_id", "directorates", ["parent_id"])


def downgrade():
    raise RuntimeError(
        "Destructive downgrade disabled. Restore the verified backup; do not drop parent links."
    )
