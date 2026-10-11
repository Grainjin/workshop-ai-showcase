"""Associate provider quote files without changing existing attachment purposes."""

import sqlalchemy as sa
from alembic import op


revision = "0014_quote_attachments"
down_revision = "0013_booking_attachment_purpose"
branch_labels = None
depends_on = None

_fk_name = "fk_booking_attachment_quote_revision"
_index_name = "ix_booking_attachments_quote_revision_id"


def upgrade() -> None:
    bind = op.get_bind()
    if "quote_revision_id" in {
        column["name"] for column in sa.inspect(bind).get_columns("booking_attachments")
    }:
        # Fresh installations already create current model metadata in 0001.
        return
    with op.batch_alter_table("booking_attachments") as batch:
        batch.add_column(sa.Column("quote_revision_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            _fk_name, "booking_quote_revisions", ["quote_revision_id"], ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(_index_name, ["quote_revision_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if "quote_revision_id" not in {
        column["name"] for column in sa.inspect(bind).get_columns("booking_attachments")
    }:
        return
    with op.batch_alter_table("booking_attachments") as batch:
        batch.drop_index(_index_name)
        # Dropping the column also removes its dependent foreign key. Avoid
        # addressing the constraint by name because fresh SQLite schemas may
        # create the model-defined foreign key without a persisted name.
        batch.drop_column("quote_revision_id")
