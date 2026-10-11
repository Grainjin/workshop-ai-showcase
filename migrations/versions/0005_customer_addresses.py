"""Add customer address book."""

import sqlalchemy as sa
from alembic import op

revision = "0005_customer_addresses"
down_revision = "0003_service_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "customer_addresses" in inspector.get_table_names():
        return
    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("place_id", sa.String(length=256), nullable=False),
        sa.Column("formatted_address", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "service_location_id",
            sa.Integer(),
            sa.ForeignKey("service_locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customer_addresses_id", "customer_addresses", ["id"])
    op.create_index("ix_customer_addresses_customer_id", "customer_addresses", ["customer_id"])
    op.create_index(
        "ix_customer_addresses_customer_created",
        "customer_addresses",
        ["customer_id", "created_at"],
    )
    op.create_index(
        "ix_customer_addresses_customer_default",
        "customer_addresses",
        ["customer_id", "is_default"],
    )
    op.create_index(
        "ix_customer_addresses_service_location_id", "customer_addresses", ["service_location_id"]
    )


def downgrade() -> None:
    if "customer_addresses" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("customer_addresses")
