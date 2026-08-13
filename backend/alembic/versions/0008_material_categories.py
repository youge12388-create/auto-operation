"""Add first-class material categories and classification state."""

import sqlalchemy as sa

from alembic import op

revision = "0008_material_categories"
down_revision = "0007_topic_algorithms"
branch_labels = None
depends_on = None

BUILTIN_CATEGORIES = (
    ("c1000000-0000-4000-8000-000000000001", "AI 前沿", "模型、研究、智能体与 AI 行业的重要进展"),
    ("c1000000-0000-4000-8000-000000000002", "产品与商业", "产品发布、商业模式、公司动态与市场机会"),
    ("c1000000-0000-4000-8000-000000000003", "技术与工具", "开发工具、开源项目、工程实践与使用教程"),
    ("c1000000-0000-4000-8000-000000000004", "行业观察", "产业趋势、人物观点、政策与社会影响"),
    ("c1000000-0000-4000-8000-000000000005", "其他", "暂时不适合前述分类，但仍有保留价值的内容"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    category_table_exists = "material_categories" in inspector.get_table_names()
    if not category_table_exists:
        op.create_table(
            "material_categories",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("classification_instructions", sa.Text(), nullable=False, server_default=""),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_material_categories_name", "material_categories", ["name"])

    category_table = sa.table(
        "material_categories",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("classification_instructions", sa.Text()),
        sa.column("enabled", sa.Boolean()),
        sa.column("is_builtin", sa.Boolean()),
    )
    existing_category_ids: set[str] = set()
    existing_category_names: set[str] = set()
    if category_table_exists:
        existing_category_ids = set(bind.execute(sa.text("SELECT id FROM material_categories")).scalars())
        existing_category_names = set(bind.execute(sa.text("SELECT name FROM material_categories")).scalars())
    missing_categories = [
        {
            "id": category_id,
            "name": name,
            "description": description,
            "classification_instructions": "",
            "enabled": True,
            "is_builtin": True,
        }
        for category_id, name, description in BUILTIN_CATEGORIES
        if category_id not in existing_category_ids and name not in existing_category_names
    ]
    if missing_categories:
        op.bulk_insert(category_table, missing_categories)

    source_columns = {column["name"] for column in inspector.get_columns("source_items")}
    source_indexes = {index["name"] for index in inspector.get_indexes("source_items")}
    new_columns = [
        ("category_id", sa.Column("category_id", sa.String(length=36), nullable=True)),
        (
            "classification_status",
            sa.Column("classification_status", sa.String(length=32), nullable=False, server_default="pending"),
        ),
        ("classification_source", sa.Column("classification_source", sa.String(length=32), nullable=True)),
        ("classification_confidence", sa.Column("classification_confidence", sa.Float(), nullable=True)),
        ("classification_reason", sa.Column("classification_reason", sa.Text(), nullable=True)),
        ("classification_error", sa.Column("classification_error", sa.Text(), nullable=True)),
    ]
    missing_column_names = {name for name, _ in new_columns if name not in source_columns}
    if missing_column_names:
        with op.batch_alter_table("source_items") as batch_op:
            for name, column in new_columns:
                if name in missing_column_names:
                    batch_op.add_column(column)
            if "category_id" in missing_column_names:
                batch_op.create_foreign_key(
                    "fk_source_items_category_id_material_categories",
                    "material_categories",
                    ["category_id"],
                    ["id"],
                )
            if "ix_source_items_category_id" not in source_indexes:
                batch_op.create_index("ix_source_items_category_id", ["category_id"])
            if "ix_source_items_classification_status" not in source_indexes:
                batch_op.create_index("ix_source_items_classification_status", ["classification_status"])
    else:
        if "ix_source_items_category_id" not in source_indexes:
            op.create_index("ix_source_items_category_id", "source_items", ["category_id"])
        if "ix_source_items_classification_status" not in source_indexes:
            op.create_index("ix_source_items_classification_status", "source_items", ["classification_status"])


def downgrade() -> None:
    with op.batch_alter_table("source_items") as batch_op:
        batch_op.drop_index("ix_source_items_classification_status")
        batch_op.drop_index("ix_source_items_category_id")
        batch_op.drop_constraint("fk_source_items_category_id_material_categories", type_="foreignkey")
        batch_op.drop_column("classification_error")
        batch_op.drop_column("classification_reason")
        batch_op.drop_column("classification_confidence")
        batch_op.drop_column("classification_source")
        batch_op.drop_column("classification_status")
        batch_op.drop_column("category_id")
    op.drop_index("ix_material_categories_name", table_name="material_categories")
    op.drop_table("material_categories")