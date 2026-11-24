"""Add an independently configurable background for sidebar navigation items."""
from alembic import op
from sqlalchemy import Column, String, inspect, text

revision = "0009_sidebar_item_background"
down_revision = "0008_print_template_settings"
branch_labels = depends_on = None


def upgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("brand_settings")}
    if "sidebar_item_bg" not in columns:
        op.add_column(
            "brand_settings",
            Column("sidebar_item_bg", String(length=7), nullable=False, server_default=text("'#edf1e8'")),
        )


def downgrade():
    raise RuntimeError("Brand settings downgrade is disabled; restore a verified database backup.")
