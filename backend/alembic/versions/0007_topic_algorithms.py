"""Add a persistent library of topic recommendation algorithms."""

import sqlalchemy as sa

from alembic import op

revision = "0007_topic_algorithms"
down_revision = "0006_topic_materials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_algorithms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("max_topics", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("weights_json", sa.JSON(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_topic_algorithms_name", "topic_algorithms", ["name"])


def downgrade() -> None:
    op.drop_index("ix_topic_algorithms_name", table_name="topic_algorithms")
    op.drop_table("topic_algorithms")