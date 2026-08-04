"""Allow one topic to reference multiple source materials."""

from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0006_topic_materials"
down_revision = "0005_job_priority"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "topic_materials" not in inspect(bind).get_table_names():
        op.create_table(
            "topic_materials",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("topic_id", sa.String(length=36), nullable=False),
            sa.Column("source_item_id", sa.String(length=36), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="supporting"),
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["topic_id"], ["topics.id"]),
            sa.ForeignKeyConstraint(["source_item_id"], ["source_items.id"]),
            sa.UniqueConstraint("topic_id", "source_item_id", name="uq_topic_material"),
        )
        op.create_index("ix_topic_materials_topic_id", "topic_materials", ["topic_id"])
        op.create_index("ix_topic_materials_source_item_id", "topic_materials", ["source_item_id"])
        rows = bind.execute(
            sa.text("SELECT id, source_item_id FROM topics WHERE source_item_id IS NOT NULL")
        ).mappings()
        topic_materials = sa.table(
            "topic_materials",
            sa.column("id", sa.String()),
            sa.column("topic_id", sa.String()),
            sa.column("source_item_id", sa.String()),
            sa.column("role", sa.String()),
            sa.column("relevance_score", sa.Float()),
        )
        op.bulk_insert(
            topic_materials,
            [
                {
                    "id": str(uuid4()),
                    "topic_id": row["id"],
                    "source_item_id": row["source_item_id"],
                    "role": "primary",
                    "relevance_score": 100.0,
                }
                for row in rows
            ],
        )


def downgrade() -> None:
    if "topic_materials" in inspect(op.get_bind()).get_table_names():
        op.drop_index("ix_topic_materials_source_item_id", table_name="topic_materials")
        op.drop_index("ix_topic_materials_topic_id", table_name="topic_materials")
        op.drop_table("topic_materials")
