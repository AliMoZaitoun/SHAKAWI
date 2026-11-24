"""Persist safe defaults for complaint print summaries."""
from alembic import op
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, inspect, text

revision = "0008_print_template_settings"
down_revision = "0007_brand_settings"
branch_labels = depends_on = None


def upgrade():
    if "print_template_settings" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "print_template_settings",
        Column("id", Integer(), primary_key=True),
        Column("titles", JSON(), nullable=False),
        Column("default_sections", JSON(), nullable=False),
        Column("updated_at", DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")),
        Column("updated_by_user_id", Integer(), ForeignKey("users.id", ondelete="RESTRICT")),
    )


def downgrade():
    raise RuntimeError("Print template downgrade is disabled; restore a verified database backup.")
