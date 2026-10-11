import importlib
import json
from datetime import datetime

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.database import Base


def test_attachment_purpose_migration_handles_fresh_model_metadata():
    migration = importlib.import_module("migrations.versions.0013_booking_attachment_purpose")
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
        purpose_column = next(
            column for column in sa.inspect(connection).get_columns("booking_attachments")
            if column["name"] == "purpose"
        )
        assert purpose_column["nullable"] is False
        assert purpose_column["default"] == "'customer_attachment'"
    engine.dispose()


def test_attachment_purpose_migration_preserves_files_and_backfills_each_source():
    migration = importlib.import_module("migrations.versions.0013_booking_attachment_purpose")
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    bookings = sa.Table(
        "bookings", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("customer_id", sa.Integer, nullable=False),
        sa.Column("arrival_started_at", sa.DateTime, nullable=True),
    )
    attachments = sa.Table(
        "booking_attachments", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("booking_id", sa.Integer, nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("original_file_name", sa.String(255), nullable=False),
        sa.Column("file_url", sa.String(1024), nullable=False),
    )
    messages = sa.Table(
        "chat_messages", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("related_id", sa.Integer),
        sa.Column("related_type", sa.String(32)),
        sa.Column("metadata_json", sa.Text),
    )
    metadata.create_all(engine)
    before_arrival = datetime(2026, 10, 1, 10, 4)
    after_arrival = datetime(2026, 10, 1, 10, 10)
    with engine.begin() as connection:
        connection.execute(bookings.insert(), [
            {"id": 1, "customer_id": 10, "arrival_started_at": datetime(2026, 10, 1, 10, 5)},
            {"id": 2, "customer_id": 11, "arrival_started_at": None},
        ])
        files = [
            {"id": attachment_id, "booking_id": booking_id, "uploaded_by_user_id": user_id,
             "created_at": created_at, "original_file_name": "photo.png",
             "file_url": f"/uploads/bookings/{booking_id}/{attachment_id}.png"}
            for attachment_id, booking_id, user_id, created_at in (
                (1, 1, 10, before_arrival),
                (2, 1, 20, before_arrival),
                (3, 1, 20, after_arrival),
                (4, 1, 20, before_arrival),
                (5, 2, 21, before_arrival),
            )
        ]
        connection.execute(attachments.insert(), files)
        connection.execute(messages.insert(), [
            {"related_id": 1, "related_type": "booking", "metadata_json": json.dumps(
                {"proof_attachments": [{"id": 4}, {"id": 1}, {"id": "invalid"}]}
            )},
            {"related_id": 2, "related_type": "booking", "metadata_json": json.dumps(
                {"proof_attachments": [{"id": 2}]}
            )},
            {"related_id": 1, "related_type": "booking", "metadata_json": "invalid json"},
            {"related_id": 1, "related_type": "booking", "metadata_json": "[]"},
        ])
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()  # Fresh/current metadata is safe to encounter again.
            migrated = sa.Table("booking_attachments", sa.MetaData(), autoload_with=connection)
            rows = connection.execute(sa.select(migrated).order_by(migrated.c.id)).mappings().all()
            assert [row["purpose"] for row in rows] == [
                "customer_attachment", "arrival_evidence", "completion_proof",
                "completion_proof", "completion_proof",
            ]
            assert [{key: row[key] for key in file} for row, file in zip(rows, files)] == files
            purpose_column = next(
                column for column in sa.inspect(connection).get_columns("booking_attachments")
                if column["name"] == "purpose"
            )
            assert purpose_column["nullable"] is False
            migration.downgrade()
            assert "purpose" not in {
                column["name"] for column in sa.inspect(connection).get_columns("booking_attachments")
            }
            restored = sa.Table("booking_attachments", sa.MetaData(), autoload_with=connection)
            assert connection.execute(sa.select(sa.func.count()).select_from(restored)).scalar_one() == 5
    engine.dispose()
