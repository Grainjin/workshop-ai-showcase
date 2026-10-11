"""Add user email and phone verification timestamps."""

import sqlalchemy as sa
from alembic import op

revision = "0002_user_verification_flags"
down_revision = "0001_initial_postgres"
branch_labels = None
depends_on = None


def _user_columns(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns("users")}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _user_columns(bind)

    if "email_verified_at" not in columns:
        op.add_column(
            "users",
            sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "phone_verified_at" not in columns:
        op.add_column(
            "users",
            sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        )

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE users AS u
            SET email_verified_at = ai.verified_at
            FROM authentication_identities AS ai
            WHERE ai.user_id = u.id
              AND ai.identity_provider = 'email_password'
              AND ai.verified_at IS NOT NULL
              AND u.email_verified_at IS NULL
            """
        )
    else:
        op.execute(
            """
            UPDATE users
            SET email_verified_at = (
                SELECT ai.verified_at
                FROM authentication_identities AS ai
                WHERE ai.user_id = users.id
                  AND ai.identity_provider = 'email_password'
                  AND ai.verified_at IS NOT NULL
            )
            WHERE email_verified_at IS NULL
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = _user_columns(bind)

    if "phone_verified_at" in columns:
        op.drop_column("users", "phone_verified_at")
    if "email_verified_at" in columns:
        op.drop_column("users", "email_verified_at")
