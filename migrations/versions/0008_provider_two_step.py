"""Add provider entity type and independent identity/qualification review."""

import sqlalchemy as sa
from alembic import op

revision = "0008_provider_two_step"
down_revision = "0007_booking_title"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("provider_profiles")}
    additions = [
        ("entity_type", sa.String(32), "personal"),
        ("identity_verification_status", sa.String(32), "pending"),
        ("qualification_verification_status", sa.String(32), "pending"),
    ]
    for name, column_type, default in additions:
        if name not in columns:
            op.add_column(
                "provider_profiles",
                sa.Column(name, column_type, nullable=True, server_default=default),
            )
    op.execute("UPDATE provider_profiles SET entity_type = COALESCE(entity_type, 'personal')")
    op.execute(
        "UPDATE provider_profiles SET identity_verification_status = CASE WHEN verification_status = 'approved' THEN 'approved' ELSE COALESCE(verification_status, 'pending') END"
    )
    op.execute(
        "UPDATE provider_profiles SET qualification_verification_status = CASE WHEN verification_status = 'approved' THEN 'approved' ELSE 'pending' END"
    )
    with op.batch_alter_table("provider_profiles") as batch_op:
        for name in ("entity_type", "identity_verification_status", "qualification_verification_status"):
            batch_op.alter_column(name, nullable=False, server_default="personal" if name == "entity_type" else "pending")
    history_columns = {
        column["name"] for column in inspector.get_columns("provider_verification_histories")
    }
    if "verification_step" not in history_columns:
        op.add_column(
            "provider_verification_histories",
            sa.Column("verification_step", sa.String(32), nullable=True, server_default="qualification"),
        )
        op.execute(
            "UPDATE provider_verification_histories SET verification_step = 'qualification' WHERE verification_step IS NULL"
        )
        with op.batch_alter_table("provider_verification_histories") as batch_op:
            batch_op.alter_column("verification_step", nullable=False, server_default="qualification")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    history_columns = {
        column["name"] for column in inspector.get_columns("provider_verification_histories")
    }
    if "verification_step" in history_columns:
        op.drop_column("provider_verification_histories", "verification_step")
    columns = {column["name"] for column in inspector.get_columns("provider_profiles")}
    for name in ("qualification_verification_status", "identity_verification_status", "entity_type"):
        if name in columns:
            op.drop_column("provider_profiles", name)
