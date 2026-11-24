"""Persist safely configurable site identity."""
from alembic import op
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, inspect, text

revision = "0007_brand_settings"
down_revision = "0006_file_policy_retention"
branch_labels = depends_on = None


def upgrade():
    if "brand_settings" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "brand_settings",
        Column("id", Integer(), primary_key=True),
        Column("brand_dark", String(length=7), nullable=False, server_default="#3b4b32"),
        Column("brand_primary", String(length=7), nullable=False, server_default="#4a5d3f"),
        Column("brand_light", String(length=7), nullable=False, server_default="#657b57"),
        Column("brand_accent", String(length=7), nullable=False, server_default="#b88d4b"),
        Column("brand_gold", String(length=7), nullable=False, server_default="#d4a860"),
        Column("brand_bg", String(length=7), nullable=False, server_default="#f7f8f4"),
        Column("brand_card", String(length=7), nullable=False, server_default="#ffffff"),
        Column("logo_path", String(length=500), nullable=True),
        Column("logo_version", Integer(), nullable=False, server_default=text("0")),
        Column("updated_at", DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")),
        Column("updated_by_user_id", Integer(), ForeignKey("users.id", ondelete="RESTRICT")),
    )


def downgrade():
    raise RuntimeError("Brand settings downgrade is disabled; restore a verified database backup.")
