"""Allow administrators to choose the citizen homepage hero decoration."""
from alembic import op
from sqlalchemy import Column, String, inspect, text

revision = "0010_brand_hero_art_style"
down_revision = "0009_sidebar_item_background"
branch_labels = depends_on = None


def upgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("brand_settings")}
    if "hero_art_style" not in columns:
        op.add_column(
            "brand_settings",
            Column(
                "hero_art_style",
                String(length=24),
                nullable=False,
                server_default=text("'flowing_lines'"),
            ),
        )


def downgrade():
    raise RuntimeError("Brand hero style downgrade is disabled; restore a verified database backup.")
