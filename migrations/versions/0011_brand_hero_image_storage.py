"""Store the public homepage image durably with brand settings."""
from alembic import op
from sqlalchemy import Column, Integer, LargeBinary, String, inspect, text

revision = "0011_brand_hero_image_storage"
down_revision = "0010_brand_hero_art_style"
branch_labels = depends_on = None


def upgrade():
    inspector = inspect(op.get_bind())
    if "brand_settings" not in inspector.get_table_names():
        raise RuntimeError("brand_settings must exist before storing the homepage image")

    columns = {column["name"] for column in inspector.get_columns("brand_settings")}
    additions = (
        ("hero_image_data", Column("hero_image_data", LargeBinary(), nullable=True)),
        ("hero_image_mime", Column("hero_image_mime", String(length=32), nullable=True)),
        (
            "hero_image_version",
            Column("hero_image_version", Integer(), nullable=False, server_default=text("0")),
        ),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("brand_settings", column)


def downgrade():
    raise RuntimeError("Homepage image storage downgrade is disabled; restore a verified database backup.")
