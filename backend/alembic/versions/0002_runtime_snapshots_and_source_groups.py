"""Add source groups and immutable article runtime snapshots."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_runtime_snapshots"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "source_groups" not in tables:
        op.create_table(
            "source_groups",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("name", name="uq_source_groups_name"),
        )
    source_columns = {column["name"] for column in inspect(bind).get_columns("sources")}
    if "group_id" not in source_columns:
        op.add_column("sources", sa.Column("group_id", sa.String(length=36), nullable=True))
        op.create_foreign_key("fk_sources_group_id", "sources", "source_groups", ["group_id"], ["id"])
    article_columns = {column["name"] for column in inspect(bind).get_columns("articles")}
    if "runtime_snapshot_json" not in article_columns:
        op.add_column(
            "articles",
            sa.Column("runtime_snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "articles" in inspector.get_table_names():
        columns = {column["name"] for column in inspect(bind).get_columns("articles")}
        if "runtime_snapshot_json" in columns:
            op.drop_column("articles", "runtime_snapshot_json")
    if "sources" in inspector.get_table_names():
        columns = {column["name"] for column in inspect(bind).get_columns("sources")}
        if "group_id" in columns:
            op.drop_constraint("fk_sources_group_id", "sources", type_="foreignkey")
            op.drop_column("sources", "group_id")
    if "source_groups" in inspector.get_table_names():
        op.drop_table("source_groups")