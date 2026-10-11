"""Store the frontend return URL used to initialize each payment checkout."""

import sqlalchemy as sa
from alembic import op


revision = "0015_payment_return_url"
down_revision = "0014_quote_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("payments")
    }
    if "frontend_return_url" not in columns:
        with op.batch_alter_table("payments") as batch:
            batch.add_column(
                sa.Column("frontend_return_url", sa.String(2048), nullable=True)
            )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("payments")
    }
    if "frontend_return_url" in columns:
        with op.batch_alter_table("payments") as batch:
            batch.drop_column("frontend_return_url")
