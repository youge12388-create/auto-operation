"""add job timing fields

Revision ID: 0003_job_timing_fields
Revises: 0002_runtime_snapshots
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_job_timing_fields"
down_revision = "0002_runtime_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("automation_jobs")}
    if "started_at" not in columns:
        op.add_column("automation_jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    if "completed_at" not in columns:
        op.add_column("automation_jobs", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    if "duration_ms" not in columns:
        op.add_column("automation_jobs", sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("automation_jobs")}
    if "duration_ms" in columns:
        op.drop_column("automation_jobs", "duration_ms")
    if "completed_at" in columns:
        op.drop_column("automation_jobs", "completed_at")
    if "started_at" in columns:
        op.drop_column("automation_jobs", "started_at")