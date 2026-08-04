"""Add an operator-facing lifecycle to collected source materials."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_material_triage"
down_revision = "0003_job_timing_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("source_items")}
    if "triage_status" not in columns:
        op.add_column(
            "source_items",
            sa.Column("triage_status", sa.String(length=32), nullable=False, server_default="inbox"),
        )
        op.create_index("ix_source_items_triage_status", "source_items", ["triage_status"])


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("source_items")}
    if "triage_status" in columns:
        op.drop_index("ix_source_items_triage_status", table_name="source_items")
        op.drop_column("source_items", "triage_status")