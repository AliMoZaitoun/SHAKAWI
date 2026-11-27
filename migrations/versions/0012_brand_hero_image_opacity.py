"""Persist the citizen homepage photo opacity setting."""
from alembic import op
from sqlalchemy import Column, Integer, inspect, text

revision = "0012_brand_hero_image_opacity"
down_revision = "0011_brand_hero_image_storage"
branch_labels = depends_on = None


def upgrade():
    inspector = inspect(op.get_bind())
    if "brand_settings" not in inspector.get_table_names():
        raise RuntimeError("brand_settings must exist before setting homepage image opacity")

    columns = {column["name"] for column in inspector.get_columns("brand_settings")}
    if "hero_image_opacity" not in columns:
        op.add_column(
            "brand_settings",
            Column(
                "hero_image_opacity",
                Integer(),
                nullable=False,
                server_default=text("85"),
            ),
        )


def downgrade():
    raise RuntimeError("Homepage image opacity downgrade is disabled; restore a verified database backup.")
