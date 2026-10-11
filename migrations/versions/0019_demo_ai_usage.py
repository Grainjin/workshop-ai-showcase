"""Persist public demo AI quotas without raw user or network identifiers."""

from alembic import op
import sqlalchemy as sa

revision = "0019_demo_ai_usage"
down_revision = "0018_booking_onboarding_pause"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 imports current ORM metadata; fresh installs can already have this table.
    if sa.inspect(op.get_bind()).has_table("demo_ai_usage"):
        return
    op.create_table(
        "demo_ai_usage",
        sa.Column("usage_date", sa.Date(), primary_key=True),
        sa.Column("subject_hash", sa.String(64), primary_key=True),
        sa.Column("daily_count", sa.Integer(), nullable=False),
        sa.Column("minute_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("minute_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("daily_count >= 0", name="ck_demo_ai_daily_nonnegative"),
        sa.CheckConstraint("minute_count >= 0", name="ck_demo_ai_minute_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("demo_ai_usage")
