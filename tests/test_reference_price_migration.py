import importlib

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_reference_price_migration_adds_nullable_indexed_service_category():
    migration = importlib.import_module(
        "migrations.versions.0017_reference_price_range"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("bookings", metadata, sa.Column("id", sa.Integer, primary_key=True))
    metadata.create_all(engine)

    with engine.begin() as connection, Operations.context(
        MigrationContext.configure(connection)
    ):
        migration.upgrade()
        inspector = sa.inspect(connection)
        column = next(
            item
            for item in inspector.get_columns("bookings")
            if item["name"] == "service_category"
        )
        assert column["nullable"] is True
        assert {
            item["name"] for item in inspector.get_indexes("bookings")
        } == {"ix_bookings_service_category"}

        migration.downgrade()
        assert "service_category" not in {
            item["name"] for item in sa.inspect(connection).get_columns("bookings")
        }

    engine.dispose()


def test_reference_price_migration_accepts_column_and_index_from_initial_schema():
    migration = importlib.import_module(
        "migrations.versions.0017_reference_price_range"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    bookings = sa.Table(
        "bookings",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("service_category", sa.String(64), nullable=True),
    )
    sa.Index("ix_bookings_service_category", bookings.c.service_category)
    metadata.create_all(engine)

    with engine.begin() as connection, Operations.context(
        MigrationContext.configure(connection)
    ):
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert "service_category" in {
            item["name"] for item in inspector.get_columns("bookings")
        }
        assert "ix_bookings_service_category" in {
            item["name"] for item in inspector.get_indexes("bookings")
        }

    engine.dispose()


def test_reference_price_migration_adds_missing_index_for_existing_column():
    migration = importlib.import_module(
        "migrations.versions.0017_reference_price_range"
    )
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table(
        "bookings",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("service_category", sa.String(64), nullable=True),
    )
    metadata.create_all(engine)

    with engine.begin() as connection, Operations.context(
        MigrationContext.configure(connection)
    ):
        migration.upgrade()
        assert "ix_bookings_service_category" in {
            item["name"]
            for item in sa.inspect(connection).get_indexes("bookings")
        }

    engine.dispose()
