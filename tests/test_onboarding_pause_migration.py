"""Exercise migrations on isolated PostgreSQL schemas, never model-created fixtures."""

from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa

from backend import config as backend_config


PAUSE_COLUMNS = {
    "onboarding_paused",
    "onboarding_pause_reason",
    "onboarding_paused_at",
}
PREVIOUS_REVISION = "0017_reference_price_range"


@pytest.fixture
def isolated_postgresql_migrations(monkeypatch):
    url = os.environ.get("WORKSHOP_MIGRATION_TEST_DATABASE_URL", backend_config.DATABASE_URL)
    if sa.engine.make_url(url).get_backend_name() != "postgresql":
        message = "Migration contract tests require a PostgreSQL database URL"
        if os.environ.get("WORKSHOP_REQUIRE_POSTGRES_MIGRATION_TESTS") == "1":
            pytest.fail(message)
        pytest.skip(message)

    # Own only this random schema; never drop or recreate a caller's database.
    schema = f"migration_test_{uuid4().hex}"
    admin_engine = sa.create_engine(url)
    with admin_engine.begin() as connection:
        connection.execute(sa.schema.CreateSchema(schema))
    migration_engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    monkeypatch.setattr(backend_config, "DATABASE_URL", url)
    monkeypatch.setenv("PGOPTIONS", f"-csearch_path={schema}")
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        yield migration_engine, alembic_config
    finally:
        migration_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.fixture
def fresh_migrated_postgresql(isolated_postgresql_migrations):
    engine, alembic_config = isolated_postgresql_migrations
    command.upgrade(alembic_config, "head")
    return engine, alembic_config


def _assert_pause_columns(connection):
    columns = {column["name"]: column for column in sa.inspect(connection).get_columns("bookings")}
    assert PAUSE_COLUMNS <= columns.keys()
    paused = columns["onboarding_paused"]
    assert isinstance(paused["type"], sa.Boolean)
    assert paused["nullable"] is False
    assert paused["default"] is not None
    assert connection.execute(sa.text(f"SELECT {paused['default']}")).scalar_one() is False
    assert columns["onboarding_pause_reason"]["type"].length == 64
    assert columns["onboarding_pause_reason"]["nullable"] is True
    assert columns["onboarding_paused_at"]["type"].timezone is True
    assert columns["onboarding_paused_at"]["nullable"] is True


def test_fresh_migration_creates_booking_onboarding_pause_columns(fresh_migrated_postgresql):
    engine, _ = fresh_migrated_postgresql
    with engine.connect() as connection:
        _assert_pause_columns(connection)


@pytest.mark.parametrize(
    "existing_columns",
    [
        (),
        ("onboarding_paused",),
        ("onboarding_pause_reason",),
        ("onboarding_paused_at",),
        tuple(sorted(PAUSE_COLUMNS)),
    ],
)
def test_existing_0017_booking_schema_upgrades_and_round_trips(
    isolated_postgresql_migrations, existing_columns
):
    engine, alembic_config = isolated_postgresql_migrations
    column_definitions = {
        "onboarding_paused": sa.Column("onboarding_paused", sa.Boolean, nullable=False),
        "onboarding_pause_reason": sa.Column("onboarding_pause_reason", sa.String(64)),
        "onboarding_paused_at": sa.Column("onboarding_paused_at", sa.DateTime(timezone=True)),
    }
    bookings = sa.Table(
        "bookings",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("payload", sa.Text, nullable=False),
        *(column_definitions[name] for name in existing_columns),
    )
    existing_values = {
        "onboarding_paused": True,
        "onboarding_pause_reason": "existing reason",
        "onboarding_paused_at": datetime(2026, 10, 1, tzinfo=timezone.utc),
    }
    with engine.begin() as connection:
        bookings.create(connection)
        connection.execute(
            bookings.insert().values(
                id=1,
                payload="preserve this booking",
                **{name: existing_values[name] for name in existing_columns},
            )
        )
    command.stamp(alembic_config, PREVIOUS_REVISION)
    command.upgrade(alembic_config, "head")
    with engine.begin() as connection:
        _assert_pause_columns(connection)
        migrated = sa.Table("bookings", sa.MetaData(), autoload_with=connection)
        row = connection.execute(sa.select(migrated)).mappings().one()
        assert row["payload"] == "preserve this booking"
        for name in existing_columns:
            assert row[name] == existing_values[name]
        if "onboarding_paused" not in existing_columns:
            assert row["onboarding_paused"] is False
        connection.execute(migrated.insert().values(id=2, payload="default is false"))
        assert (
            connection.execute(
                sa.select(migrated.c.onboarding_paused).where(migrated.c.id == 2)
            ).scalar_one()
            is False
        )

    command.downgrade(alembic_config, PREVIOUS_REVISION)
    with engine.connect() as connection:
        assert {column["name"] for column in sa.inspect(connection).get_columns("bookings")} == {
            "id",
            "payload",
        }
        assert connection.execute(
            sa.text("SELECT payload FROM bookings ORDER BY id")
        ).scalars().all() == [
            "preserve this booking",
            "default is false",
        ]
        assert (
            connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
            == PREVIOUS_REVISION
        )
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        _assert_pause_columns(connection)
