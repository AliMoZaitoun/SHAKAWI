"""Add a translated complaint-type catalog and per-complaint SLA snapshots."""
from alembic import op
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    inspect,
    text,
)

revision = "0005_complaint_types"
down_revision = "0004_system_admin"
branch_labels = depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())

    if "complaint_types" not in tables:
        op.create_table(
            "complaint_types",
            Column("id", Integer(), primary_key=True),
            Column("code", String(length=80), nullable=False),
            Column("name", String(length=50), nullable=False),
            Column("description", Text(), server_default=text("''"), nullable=False),
            Column("sla_duration_minutes", Integer(), nullable=True),
            Column("is_active", Boolean(), server_default=text("1"), nullable=False),
            Column("is_system", Boolean(), server_default=text("0"), nullable=False),
            Column("created_at", DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP")),
            CheckConstraint(
                "sla_duration_minutes IS NULL OR sla_duration_minutes > 0",
                name="ck_complaint_type_positive_sla",
            ),
            CheckConstraint(
                "code != 'other' OR sla_duration_minutes IS NULL",
                name="ck_other_complaint_type_no_sla",
            ),
            UniqueConstraint("code", name="uq_complaint_types_code"),
        )
    tables = set(inspect(connection).get_table_names())
    if "complaint_type_translations" not in tables:
        op.create_table(
            "complaint_type_translations",
            Column(
                "complaint_type_id",
                Integer(),
                ForeignKey("complaint_types.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            Column(
                "language_code",
                String(length=35),
                ForeignKey("languages.code", ondelete="RESTRICT"),
                primary_key=True,
            ),
            Column("name", String(length=150), nullable=False),
            Column("description", Text(), server_default=text("''"), nullable=False),
        )

    columns = {column["name"] for column in inspect(connection).get_columns("complaints")}
    if {"complaint_type_id", "sla_duration_minutes"} - columns:
        with op.batch_alter_table("complaints") as batch:
            if "complaint_type_id" not in columns:
                batch.add_column(
                    Column(
                        "complaint_type_id",
                        Integer(),
                        ForeignKey(
                            "complaint_types.id",
                            name="fk_complaints_complaint_type_id_complaint_types",
                        ),
                        nullable=True,
                    ),
                )
            if "sla_duration_minutes" not in columns:
                batch.add_column(Column("sla_duration_minutes", Integer(), nullable=True))

    indexes = {index["name"] for index in inspect(connection).get_indexes("complaint_types")}
    if "ix_complaint_types_code" not in indexes:
        op.create_index("ix_complaint_types_code", "complaint_types", ["code"], unique=True)
    if "ix_complaint_types_is_active" not in indexes:
        op.create_index("ix_complaint_types_is_active", "complaint_types", ["is_active"])
    indexes = {index["name"] for index in inspect(connection).get_indexes("complaints")}
    if "ix_complaints_complaint_type_id" not in indexes:
        op.create_index("ix_complaints_complaint_type_id", "complaints", ["complaint_type_id"])


def downgrade():
    raise RuntimeError(
        "Destructive downgrade disabled because complaint type and SLA records may be in use. "
        "Restore a verified database backup instead."
    )
