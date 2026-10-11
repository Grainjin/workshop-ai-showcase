"""Store hashed one-time codes for email verification, including sign-up."""

import sqlalchemy as sa
from alembic import op


revision = "0016_email_verification_codes"
down_revision = "0015_payment_return_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "email_verification_codes" in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("requested_ip", sa.String(64), nullable=True),
        sa.Column("code_salt", sa.String(64), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_email_verification_codes_id",
        "email_verification_codes",
        ["id"],
    )
    op.create_index(
        "ix_email_verification_codes_user_id",
        "email_verification_codes",
        ["user_id"],
    )
    op.create_index(
        "ix_email_verification_codes_email",
        "email_verification_codes",
        ["email"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "email_verification_codes" not in sa.inspect(bind).get_table_names():
        return

    op.drop_index(
        "ix_email_verification_codes_email",
        table_name="email_verification_codes",
    )
    op.drop_index(
        "ix_email_verification_codes_user_id",
        table_name="email_verification_codes",
    )
    op.drop_index("ix_email_verification_codes_id", table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
