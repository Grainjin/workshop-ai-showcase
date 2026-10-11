"""Store split quote details and decline metadata for direct-flow bookings."""

import sqlalchemy as sa
from alembic import op


revision = "0012_quote_split_history"
down_revision = "0011_payment_direct_flow"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    missing = [
        sa.Column("expected_service_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("visit_fee_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
    ]
    missing = [column for column in missing if column.name not in _columns("booking_quote_revisions")]
    if missing:
        with op.batch_alter_table("booking_quote_revisions") as batch:
            for column in missing:
                batch.add_column(column)


def downgrade() -> None:
    existing = _columns("booking_quote_revisions")
    removable = [
        name
        for name in (
            "expected_service_amount",
            "visit_fee_amount",
            "total_amount",
            "declined_at",
            "decline_reason",
        )
        if name in existing
    ]
    if removable:
        with op.batch_alter_table("booking_quote_revisions") as batch:
            for name in removable:
                batch.drop_column(name)
