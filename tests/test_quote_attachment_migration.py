import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.database import Base


def test_quote_attachment_migration_handles_fresh_models_and_downgrade():
    migration = importlib.import_module("migrations.versions.0014_quote_attachments")
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
        assert "quote_revision_id" in {column["name"] for column in sa.inspect(connection).get_columns("booking_attachments")}
        migration.downgrade()
        assert "quote_revision_id" not in {column["name"] for column in sa.inspect(connection).get_columns("booking_attachments")}
        migration.upgrade()
        assert sa.inspect(connection).get_foreign_keys("booking_attachments")
    engine.dispose()


def test_quote_attachment_migration_preserves_existing_files_and_null_associations():
    migration = importlib.import_module("migrations.versions.0014_quote_attachments")
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("booking_quote_revisions", metadata, sa.Column("id", sa.Integer, primary_key=True))
    attachments = sa.Table("booking_attachments", metadata,
                           sa.Column("id", sa.Integer, primary_key=True),
                           sa.Column("purpose", sa.String(32), nullable=False),
                           sa.Column("file_url", sa.String(1024), nullable=False))
    metadata.create_all(engine)
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        connection.execute(attachments.insert(), [
            {"id": 1, "purpose": "customer_attachment", "file_url": "/uploads/a.png"},
            {"id": 2, "purpose": "completion_proof", "file_url": "/uploads/b.png"},
        ])
        migration.upgrade()
        migration.upgrade()
        migrated = sa.Table("booking_attachments", sa.MetaData(), autoload_with=connection)
        rows = connection.execute(sa.select(migrated).order_by(migrated.c.id)).mappings().all()
        assert [row["quote_revision_id"] for row in rows] == [None, None]
        assert [row["file_url"] for row in rows] == ["/uploads/a.png", "/uploads/b.png"]
        assert [row["purpose"] for row in rows] == ["customer_attachment", "completion_proof"]
        migration.downgrade()
        assert connection.execute(sa.select(sa.func.count()).select_from(attachments)).scalar_one() == 2
    engine.dispose()
