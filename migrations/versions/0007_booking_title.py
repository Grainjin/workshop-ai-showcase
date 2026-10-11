"""Add the required title for booking requests."""

import sqlalchemy as sa
from alembic import op

revision = "0007_booking_title"
down_revision = "0006_merge_ws91_ws98"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("bookings")}
    if "title" not in columns:
        op.add_column("bookings", sa.Column("title", sa.Text(), nullable=True))
        op.execute("UPDATE bookings SET title = 'Booking' WHERE title IS NULL")
        with op.batch_alter_table("bookings") as batch_op:
            batch_op.alter_column("title", nullable=False, server_default=None)


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("bookings")}
    if "title" in columns:
        op.drop_column("bookings", "title")
