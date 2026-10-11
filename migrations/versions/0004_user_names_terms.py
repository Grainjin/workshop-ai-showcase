"""Add split personal names and Terms acceptance to users.

Existing name-only and social-login records remain valid with NULL split fields.
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_user_names_terms"
down_revision = "0003_service_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 builds from live metadata, so a fresh database may already have these columns.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "first_name" not in columns:
        op.add_column("users", sa.Column("first_name", sa.String(length=255), nullable=True))
    if "last_name" not in columns:
        op.add_column("users", sa.Column("last_name", sa.String(length=255), nullable=True))
    if "tos_accepted_at" not in columns:
        op.add_column(
            "users", sa.Column("tos_accepted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    op.drop_column("users", "tos_accepted_at")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
