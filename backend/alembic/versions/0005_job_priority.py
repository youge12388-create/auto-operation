"""Add job priority column, prepare for Redis removal."""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0005_job_priority"
down_revision = "0004_material_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("automation_jobs")}
    if "priority" not in columns:
        op.add_column(
            "automation_jobs",
            sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_automation_jobs_priority", "automation_jobs", ["priority"])


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("automation_jobs")}
    if "priority" in columns:
        op.drop_index("ix_automation_jobs_priority", table_name="automation_jobs")
        op.drop_column("automation_jobs", "priority")
