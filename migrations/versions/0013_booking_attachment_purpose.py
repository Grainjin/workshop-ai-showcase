"""Separate customer attachments, arrival evidence, and completion proof."""

import json

import sqlalchemy as sa
from alembic import op


revision = "0013_booking_attachment_purpose"
down_revision = "0012_quote_split_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"]: column for column in sa.inspect(bind).get_columns("booking_attachments")}
    if "purpose" in columns and not columns["purpose"]["nullable"]:
        # Fresh installs create the current model through the initial migration.
        return
    if "purpose" not in columns:
        op.add_column("booking_attachments", sa.Column("purpose", sa.String(32), nullable=True))

    metadata = sa.MetaData()
    attachments = sa.Table("booking_attachments", metadata, autoload_with=bind)
    bookings = sa.Table("bookings", metadata, autoload_with=bind)
    purposes = bind.execute(
        sa.select(
            attachments.c.id,
            sa.case(
                (attachments.c.uploaded_by_user_id == bookings.c.customer_id, "customer_attachment"),
                (
                    sa.and_(
                        bookings.c.arrival_started_at.is_not(None),
                        attachments.c.created_at <= bookings.c.arrival_started_at,
                    ),
                    "arrival_evidence",
                ),
                else_="completion_proof",
            ).label("purpose"),
        )
        .join(bookings, attachments.c.booking_id == bookings.c.id)
        .where(attachments.c.purpose.is_(None))
    ).all()
    if purposes:
        bind.execute(
            attachments.update()
            .where(attachments.c.id == sa.bindparam("attachment_id"))
            .values(purpose=sa.bindparam("attachment_purpose")),
            [{"attachment_id": row.id, "attachment_purpose": row.purpose} for row in purposes],
        )

    # Completion messages contain exact proof IDs; these override timestamp inference.
    messages = sa.Table("chat_messages", metadata, autoload_with=bind)
    proof_messages = bind.execute(
        sa.select(messages.c.related_id, messages.c.metadata_json)
        .where(messages.c.related_type == "booking", messages.c.metadata_json.is_not(None))
    ).all()
    for booking_id, raw_metadata in proof_messages:
        try:
            data = json.loads(raw_metadata)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict) or not isinstance(data.get("proof_attachments"), list):
            continue
        proof_ids = [
            proof["id"]
            for proof in data["proof_attachments"]
            if isinstance(proof, dict) and type(proof.get("id")) is int
        ]
        if proof_ids:
            bind.execute(
                attachments.update()
                .where(
                    attachments.c.booking_id == booking_id,
                    attachments.c.id.in_(proof_ids),
                    attachments.c.purpose != "customer_attachment",
                )
                .values(purpose="completion_proof")
            )

    with op.batch_alter_table("booking_attachments") as batch:
        batch.alter_column(
            "purpose", existing_type=sa.String(32), nullable=False,
            server_default="customer_attachment",
        )


def downgrade() -> None:
    with op.batch_alter_table("booking_attachments") as batch:
        batch.drop_column("purpose")
