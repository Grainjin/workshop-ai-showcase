"""Add the direct two-stage iyzico payment flow to the latest main schema."""

import sqlalchemy as sa
from alembic import op


revision = "0011_payment_direct_flow"
down_revision = "0010_qualification_areas"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_columns(table_name: str, columns: tuple[sa.Column, ...]) -> None:
    missing = [column for column in columns if column.name not in _columns(table_name)]
    if missing:
        with op.batch_alter_table(table_name) as batch:
            for column in missing:
                batch.add_column(column)


def upgrade() -> None:
    _add_columns(
        "bookings",
        (
            sa.Column("expected_service_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("visit_fee_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("final_quote_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("final_quote_message", sa.Text(), nullable=True),
            sa.Column("arrival_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("final_quote_declined_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("final_quote_decline_reason", sa.Text(), nullable=True),
            sa.Column("final_quote_confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("closed_reason", sa.String(64), nullable=True),
        ),
    )
    _add_columns(
        "payments",
        (
            sa.Column("payment_stage", sa.String(32), nullable=False, server_default="service_fee"),
            sa.Column("conversation_id", sa.String(128), nullable=True),
            sa.Column("basket_id", sa.String(128), nullable=True),
            sa.Column("iyzico_token", sa.String(255), nullable=True),
            sa.Column("checkout_url", sa.String(2048), nullable=True),
            sa.Column("iyzico_payment_id", sa.String(128), nullable=True),
            sa.Column("payment_transaction_id", sa.String(128), nullable=True),
            sa.Column("external_status", sa.String(64), nullable=True),
            sa.Column("failure_code", sa.String(64), nullable=True),
            sa.Column("failure_message", sa.Text(), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("idempotency_key", sa.String(128), nullable=True),
            sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("checkout_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("capture_failed_at", sa.DateTime(timezone=True), nullable=True),
        ),
    )
    _add_columns(
        "refund_requests",
        (
            sa.Column("refund_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("external_refund_id", sa.String(128), nullable=True),
            sa.Column("failure_code", sa.String(64), nullable=True),
            sa.Column("failure_message", sa.Text(), nullable=True),
        ),
    )
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("refund_requests"):
        bind.execute(
            sa.text(
                "UPDATE refund_requests SET refund_amount = "
                "(SELECT amount FROM payments WHERE payments.id = refund_requests.payment_id) "
                "WHERE refund_amount IS NULL"
            )
        )
        with op.batch_alter_table("refund_requests") as batch:
            batch.alter_column("refund_amount", existing_type=sa.Numeric(12, 2), nullable=False)

    if not inspector.has_table("provider_submerchants"):
        op.create_table(
            "provider_submerchants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider_profile_id", sa.Integer(), sa.ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("submerchant_type", sa.String(32), nullable=False),
            sa.Column("submerchant_external_id", sa.String(128), nullable=False),
            sa.Column("submerchant_key", sa.String(255)),
            sa.Column("name", sa.String(255)),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("gsm_number", sa.String(64), nullable=False),
            sa.Column("address", sa.String(512), nullable=False),
            sa.Column("iban", sa.String(64)),
            sa.Column("contact_name", sa.String(128)),
            sa.Column("contact_surname", sa.String(128)),
            sa.Column("identity_number", sa.String(64)),
            sa.Column("tax_office", sa.String(128)),
            sa.Column("tax_number", sa.String(64)),
            sa.Column("legal_company_title", sa.String(255)),
            sa.Column("currency", sa.String(8), nullable=False, server_default="TRY"),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("iyzico_error_code", sa.String(64)),
            sa.Column("iyzico_error_message", sa.Text()),
            sa.Column("last_synced_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("provider_profile_id", name="uq_provider_submerchant_provider_profile"),
            sa.UniqueConstraint("submerchant_external_id", name="uq_provider_submerchant_external_id"),
        )
    if not inspector.has_table("payment_settlements"):
        op.create_table(
            "payment_settlements",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider_profile_id", sa.Integer(), sa.ForeignKey("provider_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform_commission_rate", sa.Numeric(6, 5), nullable=False),
            sa.Column("platform_commission_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("provider_share_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("payment_transaction_id", sa.String(128)),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("approve_requested_at", sa.DateTime(timezone=True)),
            sa.Column("approved_at", sa.DateTime(timezone=True)),
            sa.Column("failure_code", sa.String(64)),
            sa.Column("failure_message", sa.Text()),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("iyzico_commission_rate_amount", sa.Numeric(12, 2)),
            sa.Column("iyzico_commission_fee", sa.Numeric(12, 2)),
            sa.Column("blockage_rate", sa.Numeric(12, 8)),
            sa.Column("blockage_resolved_at", sa.DateTime(timezone=True)),
            sa.Column("provider_payout_amount", sa.Numeric(12, 2)),
            sa.Column("merchant_payout_amount", sa.Numeric(12, 2)),
            sa.Column("provider_recovery_amount", sa.Numeric(12, 2)),
            sa.Column("recovery_status", sa.String(32)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("payment_id", name="uq_payment_settlement_payment"),
        )
    if not inspector.has_table("booking_quote_revisions"):
        op.create_table(
            "booking_quote_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
            sa.Column("revision_number", sa.Integer(), nullable=False),
            sa.Column("quote_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("quote_message", sa.Text()),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("customer_confirmed_at", sa.DateTime(timezone=True)),
            sa.Column("used_for_payment_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("booking_id", "revision_number", name="uq_booking_quote_revision_number"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("booking_quote_revisions", "payment_settlements", "provider_submerchants"):
        if sa.inspect(bind).has_table(table):
            op.drop_table(table)
