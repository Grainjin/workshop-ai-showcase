"""Quota concurrency is tested only on real PostgreSQL, in an owned schema."""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timedelta, timezone
from threading import Barrier, Event
from types import SimpleNamespace

from alembic import command
import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import config, models
from backend.utils import demo_ai_quota
from backend.utils.demo_ai_quota import consume_demo_ai_quota
from test_onboarding_pause_migration import isolated_postgresql_migrations  # noqa: F401

NOW = datetime(2026, 10, 10, 12, 30, 20, tzinfo=timezone.utc)


@pytest.fixture
def quota_engine(isolated_postgresql_migrations, monkeypatch):
    engine, _ = isolated_postgresql_migrations
    models.DemoAIUsage.__table__.create(engine)
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", 3)
    monkeypatch.setattr(config, "DEMO_AI_PER_MINUTE_LIMIT", 2)
    return engine


def consume(engine, now=NOW, subject="user:42"):
    with Session(engine) as db:
        return consume_demo_ai_quota(subject, db, now)


def test_boundaries_and_utc_day_reset(quota_engine):
    first = consume(quota_engine)
    assert (first.allowed, first.remaining_daily, first.retry_after_seconds) == (True, 2, None)
    assert consume(quota_engine).allowed
    blocked = consume(quota_engine)
    assert (blocked.allowed, blocked.remaining_daily, blocked.retry_after_seconds) == (False, 1, 40)
    assert consume(quota_engine, NOW + timedelta(seconds=40)).allowed
    daily = consume(quota_engine, NOW + timedelta(seconds=41))
    assert (daily.allowed, daily.remaining_daily, daily.retry_after_seconds) == (False, 0, 41339)
    assert consume(quota_engine, datetime(2026, 10, 11, tzinfo=timezone.utc)).remaining_daily == 2


def test_equivalent_timezone_and_separate_subject(quota_engine):
    assert consume(quota_engine).allowed
    local = NOW.astimezone(timezone(timedelta(hours=11)))
    assert consume(quota_engine, local).allowed
    assert not consume(quota_engine, local).allowed
    assert consume(quota_engine, local, "user:43").allowed


@pytest.mark.parametrize("daily,minute,seed", [(3, 20, 0), (20, 3, 0), (3, 20, 2), (20, 3, 2)])
def test_concurrent_transactions_never_overshoot(quota_engine, monkeypatch, daily, minute, seed):
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", daily)
    monkeypatch.setattr(config, "DEMO_AI_PER_MINUTE_LIMIT", minute)
    for _ in range(seed):
        assert consume(quota_engine).allowed
    barrier = Barrier(12)

    def contender(_):
        with Session(quota_engine) as db:
            # Each worker owns a real transaction/connection before releasing the barrier.
            db.execute(sa.text("SELECT 1"))
            barrier.wait(timeout=20)
            return consume_demo_ai_quota("user:42", db, NOW)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(contender, range(12)))
    assert sum(result.allowed for result in results) == 3 - seed
    with Session(quota_engine) as db:
        row = db.query(models.DemoAIUsage).one()
        assert row.daily_count == row.minute_count == 3


def test_charge_survives_caller_rollback_and_stores_only_hash(quota_engine):
    with Session(quota_engine) as db:
        db.execute(sa.text("CREATE TEMP TABLE caller_work (value integer)"))
        assert consume_demo_ai_quota("ip:192.0.2.12", db, NOW).allowed
        db.rollback()
        assert db.execute(sa.text("SELECT to_regclass('caller_work')")).scalar() is None
        row = db.query(models.DemoAIUsage).one()
        assert row.daily_count == 1
        assert len(row.subject_hash) == 64
        assert "192.0.2.12" not in repr(row.__dict__)


def test_disabled_mode_never_touches_database(monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    assert consume_demo_ai_quota("user:42", None, NOW).allowed


def test_quota_migration_upgrade_downgrade(isolated_postgresql_migrations):
    engine, alembic_config = isolated_postgresql_migrations
    # Represent an existing 0018 database, independent of 0001's current ORM imports.
    command.stamp(alembic_config, "0018_booking_onboarding_pause")
    command.upgrade(alembic_config, "head")
    columns = {c["name"] for c in sa.inspect(engine).get_columns("demo_ai_usage")}
    assert columns == {"usage_date", "subject_hash", "daily_count", "minute_start", "minute_count"}
    command.downgrade(alembic_config, "0018_booking_onboarding_pause")
    assert "demo_ai_usage" not in sa.inspect(engine).get_table_names()
    command.upgrade(alembic_config, "head")
    assert "demo_ai_usage" in sa.inspect(engine).get_table_names()


@pytest.mark.parametrize("daily,minute", [(3, 20), (20, 3)])
def test_saturated_caller_pool_still_admits_or_limits_requests(
    quota_engine, monkeypatch, daily, minute
):
    with quota_engine.connect() as connection:
        schema = connection.execute(sa.text("SELECT current_schema()")).scalar_one()
    # Explicit options must survive cloning; URL/environment alone is insufficient.
    monkeypatch.delenv("PGOPTIONS", raising=False)
    caller_engine = sa.create_engine(
        quota_engine.url, pool_size=5, max_overflow=10, pool_timeout=0.2,
        connect_args={"options": f"-csearch_path={schema}", "application_name": "quota-saturation"},
    )
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", daily)
    monkeypatch.setattr(config, "DEMO_AI_PER_MINUTE_LIMIT", minute)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz)

    monkeypatch.setattr(demo_ai_quota, "datetime", FixedDateTime)
    ready, finished = Barrier(15), Barrier(15)

    def contender(_):
        with Session(caller_engine) as db:
            db.execute(sa.text("SELECT 1"))
            ready.wait(timeout=20)
            try:
                demo_ai_quota.enforce_demo_ai_quota(SimpleNamespace(id=42), db)
                outcome = 200
            except HTTPException as error:
                outcome = error.status_code
                assert error.detail["code"] == "DEMO_AI_LIMIT_REACHED"
            except Exception as error:
                outcome = type(error).__name__
            finally:
                # No caller connection is released until every quota attempt finishes.
                finished.wait(timeout=20)
            return outcome

    try:
        with ThreadPoolExecutor(max_workers=15) as pool:
            outcomes = list(pool.map(contender, range(15)))
        assert sorted(outcomes, key=str) == [200] * 3 + [429] * 12, outcomes
        with Session(caller_engine) as db:
            row = db.query(models.DemoAIUsage).one()
            assert row.daily_count == row.minute_count == 3
        with demo_ai_quota.get_demo_ai_quota_engine(caller_engine).connect() as connection:
            assert connection.execute(sa.text("SHOW application_name")).scalar_one() == "quota-saturation"
            assert connection.execute(sa.text("SELECT current_schema()")).scalar_one() == schema
    finally:
        caller_engine.dispose()


def test_quota_pool_is_bounded_reused_and_disposed_on_app_shutdown(quota_engine):
    from fastapi.testclient import TestClient
    from backend.main import app

    with quota_engine.connect() as connection:
        schema = connection.execute(sa.text("SELECT current_schema()")).scalar_one()
    with TestClient(app):
        dedicated = demo_ai_quota.get_demo_ai_quota_engine(quota_engine)
        assert dedicated is not quota_engine
        assert demo_ai_quota.get_demo_ai_quota_engine(quota_engine) is dedicated
        attempted = Event()

        def third_connection():
            attempted.set()
            with dedicated.connect() as connection:
                return connection.execute(sa.text("SELECT current_schema()")).scalar_one()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with dedicated.connect() as first, dedicated.connect() as second:
                assert first.execute(sa.text("SELECT current_schema()")).scalar_one() == schema
                assert second.execute(sa.text("SELECT current_schema()")).scalar_one() == schema
                assert dedicated.pool.checkedout() == dedicated.pool.size() == 2
                assert dedicated.pool.overflow() == 0
                waiting = pool.submit(third_connection)
                assert attempted.wait(timeout=10)
                with pytest.raises(FutureTimeoutError):
                    waiting.result(timeout=0.2)
            assert waiting.result(timeout=10) == schema
        assert dedicated.pool.checkedin() == 2
    assert dedicated.pool.checkedin() == 0
    assert demo_ai_quota.get_demo_ai_quota_engine(quota_engine) is not dedicated


def test_quota_pool_preserves_creator_connection_hooks_and_execution_options(
    quota_engine, monkeypatch
):
    import psycopg

    with quota_engine.connect() as connection:
        schema = connection.execute(sa.text("SELECT current_schema()")).scalar_one()
    monkeypatch.delenv("PGOPTIONS", raising=False)
    created_records = []

    def creator(connection_record):
        created_records.append(connection_record)
        return psycopg.connect(
            quota_engine.url.render_as_string(hide_password=False).replace("+psycopg", ""),
            options=f"-csearch_path={schema}", sslmode="disable",
        )

    source = sa.create_engine(quota_engine.url, creator=creator)

    @sa.event.listens_for(source, "connect")
    def connection_setup(connection, record):
        # Connection setup must also run on the dedicated quota pool.
        with connection.cursor() as cursor:
            cursor.execute("SET application_name = 'quota-connect-hook'")
        connection.commit()

    @sa.event.listens_for(source, "engine_connect")
    def engine_setup(connection):
        connection.info["engine_setup"] = True

    try:
        source.update_execution_options(schema_translate_map={None: schema})
        dedicated = demo_ai_quota.get_demo_ai_quota_engine(source)
        assert dedicated.url == source.url
        assert dedicated.dialect is source.dialect
        with dedicated.connect() as connection:
            assert connection.get_execution_options()["schema_translate_map"] == {None: schema}
            assert connection.info["engine_setup"] is True
            assert connection.execute(sa.text("SELECT current_schema()")).scalar_one() == schema
            assert connection.execute(sa.text("SHOW application_name")).scalar_one() == "quota-connect-hook"
        assert len(created_records) == 1
        assert created_records[0] is not None  # SQLAlchemy's record-aware creator contract.
        assert consume(source).allowed
        assert len(created_records) == 1
        assert dedicated.pool.checkedin() == 1
        source.dispose()
        assert dedicated.pool.checkedin() == 0
        rebuilt = demo_ai_quota.get_demo_ai_quota_engine(source)
        assert rebuilt is not dedicated
        with rebuilt.connect() as connection:
            assert connection.info["engine_setup"] is True
        source.update_execution_options(schema_translate_map={None: "public"})
        updated = demo_ai_quota.get_demo_ai_quota_engine(source)
        assert updated is not rebuilt
        assert rebuilt.pool.checkedin() == 0
        assert updated.get_execution_options()["schema_translate_map"] == {None: "public"}
    finally:
        source.dispose()
