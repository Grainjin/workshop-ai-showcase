"""Restore booking onboarding pause state for existing databases."""

import sqlalchemy as sa
from alembic import op


revision = "0018_booking_onboarding_pause"
down_revision = "0017_reference_price_range"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]: column for column in sa.inspect(op.get_bind()).get_columns("bookings")
    }
    with op.batch_alter_table("bookings") as batch:
        if "onboarding_paused" not in columns:
            batch.add_column(
                sa.Column(
                    "onboarding_paused",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        elif columns["onboarding_paused"]["default"] is None:
            # 0001 creates current model metadata with a Python-only default.
            batch.alter_column(
                "onboarding_paused",
                existing_type=sa.Boolean(),
                existing_nullable=False,
                server_default=sa.false(),
            )
        if "onboarding_pause_reason" not in columns:
            batch.add_column(sa.Column("onboarding_pause_reason", sa.String(64), nullable=True))
        if "onboarding_paused_at" not in columns:
            batch.add_column(
                sa.Column(
                    "onboarding_paused_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                )
            )


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("bookings")}
    with op.batch_alter_table("bookings") as batch:
        for name in ("onboarding_paused_at", "onboarding_pause_reason", "onboarding_paused"):
            if name in columns:
                batch.drop_column(name)
