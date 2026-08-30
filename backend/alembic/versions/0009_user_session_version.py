"""Add per-user session revocation versions."""

import sqlalchemy as sa

from alembic import op

revision = "0009_user_session_version"
down_revision = "0008_material_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    user_columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "session_version" not in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(
                sa.Column("session_version", sa.Integer(), nullable=False, server_default="1")
            )


def downgrade() -> None:
    bind = op.get_bind()
    user_columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "session_version" in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("session_version")
