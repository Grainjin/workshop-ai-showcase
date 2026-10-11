"""Store the canonical service category selected for a booking."""

import sqlalchemy as sa
from alembic import op


revision = "0017_reference_price_range"
down_revision = "0016_email_verification_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("bookings")
    }
    if "service_category" not in columns:
        with op.batch_alter_table("bookings") as batch:
            batch.add_column(
                sa.Column("service_category", sa.String(64), nullable=True)
            )

    indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("bookings")
    }
    if "ix_bookings_service_category" not in indexes:
        with op.batch_alter_table("bookings") as batch:
            batch.create_index(
                "ix_bookings_service_category", ["service_category"], unique=False
            )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("bookings")
    }
    if "ix_bookings_service_category" in indexes:
        with op.batch_alter_table("bookings") as batch:
            batch.drop_index("ix_bookings_service_category")

    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("bookings")
    }
    if "service_category" in columns:
        with op.batch_alter_table("bookings") as batch:
            batch.drop_column("service_category")
