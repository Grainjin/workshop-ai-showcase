"""Reset tests own newly created databases; never reset the suite/source database."""

import importlib
import os
import random
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from backend import config, models
from backend.core.clock import utc_now
from backend.database import Base
from backend.utils.reference_price import calculate_reference_price_range


def reset_module():
    try:
        return importlib.import_module("backend.reset_demo_data")
    except ModuleNotFoundError:
        pytest.fail("Guarded demo reset has not been implemented")


@pytest.mark.parametrize("enabled,confirmation,url,marker", [
    (False, "reset-workshop-demo", "postgresql+psycopg://localhost/workshop_demo", "workshop_demo"),
    (True, "RESET-workshop-demo", "postgresql+psycopg://localhost/workshop_demo", "workshop_demo"),
    (True, "reset-workshop-demo ", "postgresql+psycopg://localhost/workshop_demo", "workshop_demo"),
    (True, "reset-workshop-demo", "postgresql+psycopg://workshop_demo@localhost/production", "workshop_demo"),
    (True, "reset-workshop-demo", "postgresql+psycopg://workshop_demo/production", "workshop_demo"),
    (True, "reset-workshop-demo", "postgresql+psycopg://localhost/production?application_name=workshop_demo", "workshop_demo"),
    (True, "reset-workshop-demo", "sqlite:///workshop_demo", "workshop_demo"),
    (True, "reset-workshop-demo", "postgresql+psycopg://localhost/workshop_demo", "custom_demo"),
    (True, "reset-workshop-demo", "postgresql+psycopg://localhost/workshop_demo", ""),
])
def test_refuses_unsafe_reset_before_connecting(monkeypatch, enabled, confirmation, url, marker):
    reset = reset_module()
    monkeypatch.setattr(config, "DEMO_MODE", enabled)
    monkeypatch.setattr(config, "DEMO_DATABASE_MARKER", marker)
    def forbidden_connection():
        pytest.fail("Refusal must happen before opening a database connection")
    engine = sa.create_engine(url, creator=forbidden_connection)
    try:
        with Session(engine) as db, pytest.raises(ValueError):
            reset.reset_demo_database(db, confirmation)
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def owned_demo_engine():
    url = sa.engine.make_url(os.environ.get(
        "WORKSHOP_RESET_TEST_ADMIN_URL", config.DATABASE_URL,
    ))
    if url.get_backend_name() != "postgresql":
        pytest.skip("Set WORKSHOP_RESET_TEST_ADMIN_URL to enable real PostgreSQL reset tests")
    name = f"workshop_demo_task7_{uuid4().hex[:12]}"
    admin = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(sa.text(f'CREATE DATABASE "{name}"'))
    target_url = url.set(database=name).render_as_string(hide_password=False)
    engine = sa.create_engine(target_url)
    print(f"TASK7_OWNED_DATABASE={name}")
    patch = pytest.MonkeyPatch()
    patch.setattr(config, "DATABASE_URL", target_url)
    try:
        command.upgrade(Config("alembic.ini"), "head")
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE unrelated_keep (value text)"))
            connection.execute(sa.text("INSERT INTO unrelated_keep VALUES ('preserve me')"))
        yield engine
    finally:
        patch.undo()
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(sa.text(f'DROP DATABASE "{name}"'))
        admin.dispose()


@pytest.fixture
def reset_ready(owned_demo_engine, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_DATABASE_MARKER", "workshop_demo")
    monkeypatch.setattr(config, "WORKSHOP_DEMO_SEED", 42)
    return reset_module(), owned_demo_engine


def snapshot(db):
    counts = {table.name: db.scalar(sa.select(sa.func.count()).select_from(table))
              for table in Base.metadata.tables.values()}
    users = db.execute(sa.select(models.User.id, models.User.email, models.User.role)
                       .order_by(models.User.id)).all()
    bookings = db.execute(sa.select(
        models.Booking.id, models.Booking.customer_id, models.Booking.provider_profile_id,
        models.Booking.status, models.Booking.service_category, models.Booking.quote_amount,
    ).order_by(models.Booking.id)).all()
    providers = db.execute(sa.select(
        models.ProviderProfile.id, models.ProviderProfile.business_name,
        models.ProviderProfile.hourly_rate, models.ProviderProfile.latitude,
    ).order_by(models.ProviderProfile.id)).all()
    ranges = [calculate_reference_price_range(booking, db) for booking in
              db.scalars(sa.select(models.Booking).where(models.Booking.id.in_([1, 41, 91])))]
    return counts, users, bookings, providers, ranges


def mutate(db):
    booking = db.get(models.Booking, 1)
    booking.status = "cancelled"
    pair = dict(customer_id=booking.customer_id, provider_profile_id=booking.provider_profile_id)
    db.add(models.FavoriteProvider(**pair))
    room = models.ChatRoom(**pair)
    db.add(room)
    db.flush()
    db.add(models.ChatMessage(chat_room_id=room.id, sender_id=booking.customer_id, message="visitor"))
    payment = models.Payment(booking_id=booking.id, amount=100, payment_method="demo", **pair)
    db.add(payment)
    db.flush()
    db.add(models.RefundRequest(booking_id=booking.id, payment_id=payment.id, reason="demo",
        previous_booking_status="completed", refund_amount=100, **pair))
    db.add(models.PaymentSettlement(payment_id=payment.id, booking_id=booking.id,
        provider_profile_id=booking.provider_profile_id, platform_commission_rate="0.1",
        platform_commission_amount=10, provider_share_amount=90))
    db.add(models.DemoAIUsage(usage_date=utc_now().date(), subject_hash="a" * 64,
        daily_count=3, minute_start=utc_now(), minute_count=1))
    db.commit()


def test_reset_is_deterministic_and_limited_to_application_tables(reset_ready):
    reset, engine = reset_ready
    state = random.getstate()
    with Session(engine) as db:
        first_result = reset.reset_demo_database(db, "reset-workshop-demo")
        original = snapshot(db)
        assert original[0]["users"] == 36
        assert original[0]["provider_profiles"] == 30
        assert original[0]["bookings"] == original[0]["booking_quote_revisions"] == 300
        assert all(row[3] == "completed" for row in original[2])
        assert all(item["has_history"] and item["sample_count"] == 29 for item in original[4])
        mutate(db)
        second_result = reset.reset_demo_database(db, "reset-workshop-demo")
        assert second_result == first_result
        assert snapshot(db) == original
        assert db.scalar(sa.text("SELECT value FROM unrelated_keep")) == "preserve me"
        assert db.scalar(sa.text("SELECT version_num FROM alembic_version")) == "0019_demo_ai_usage"
        db.rollback()
        reset.reset_demo_database(db, "reset-workshop-demo")
        assert snapshot(db) == original
    assert random.getstate() == state


def test_seed_failure_rolls_back_rows_and_identities(reset_ready, monkeypatch):
    reset, engine = reset_ready
    with Session(engine) as db:
        reset.reset_demo_database(db, "reset-workshop-demo")
        mutate(db)
        before = snapshot(db)
        sequence_before = db.execute(sa.text("SELECT last_value, is_called FROM users_id_seq")).one()
        db.rollback()
        def fail_after_seed(session, *args, **kwargs):
            from backend.seed_demo_data import create_demo_admin
            create_demo_admin(session)
            session.flush()
            raise RuntimeError("injected seed failure")
        monkeypatch.setattr(reset, "seed_demo_data", fail_after_seed)
        with pytest.raises(RuntimeError, match="injected seed failure"):
            reset.reset_demo_database(db, "reset-workshop-demo")
        assert not db.in_transaction()
        assert snapshot(db) == before
        assert db.execute(sa.text("SELECT last_value, is_called FROM users_id_seq")).one() == sequence_before
        assert db.scalar(sa.select(models.ChatMessage.message)) == "visitor"


def test_refuses_concurrent_reset_before_truncate(reset_ready):
    reset, engine = reset_ready
    with Session(engine) as holder, Session(engine) as contender:
        holder.execute(sa.text("SELECT pg_advisory_xact_lock(hashtext('workshop-demo-reset'))"))
        with pytest.raises(ValueError, match="already running"):
            reset.reset_demo_database(contender, "reset-workshop-demo")


def test_refuses_existing_transaction(reset_ready):
    reset, engine = reset_ready
    with Session(engine) as db:
        db.execute(sa.text("SELECT 1"))
        with pytest.raises(ValueError, match="transaction"):
            reset.reset_demo_database(db, "reset-workshop-demo")


def test_refuses_autocommit_before_truncate(reset_ready):
    reset, engine = reset_ready
    unsafe = engine.execution_options(isolation_level="AUTOCOMMIT")
    with Session(unsafe) as db, pytest.raises(ValueError, match="autocommit"):
        reset.reset_demo_database(db, "reset-workshop-demo")


def test_refuses_connection_database_override(reset_ready):
    reset, engine = reset_ready
    # Safe URL lies about its database; the actual connection still targets our owned DB.
    connect_args, connect_kwargs = engine.dialect.create_connect_args(engine.url)
    misleading = sa.create_engine(engine.url.set(database="workshop_demo_wrong"),
                                 creator=lambda: engine.dialect.dbapi.connect(
                                     *connect_args, **connect_kwargs))
    try:
        with Session(misleading) as db, pytest.raises(ValueError, match="Connected database"):
            reset.reset_demo_database(db, "reset-workshop-demo")
    finally:
        misleading.dispose()


def test_unknown_foreign_key_dependency_does_not_expand_truncate_scope(reset_ready):
    reset, engine = reset_ready
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE unrelated_fk (user_id integer REFERENCES users(id))"))
        connection.execute(sa.text("INSERT INTO unrelated_fk SELECT min(id) FROM users"))
    try:
        with Session(engine) as db:
            before = snapshot(db)
            db.rollback()
            with pytest.raises(sa.exc.DBAPIError):
                reset.reset_demo_database(db, "reset-workshop-demo")
            assert snapshot(db) == before
            assert db.scalar(sa.text("SELECT count(*) FROM unrelated_fk")) == 1
    finally:
        with engine.begin() as connection:
            connection.execute(sa.text("DROP TABLE unrelated_fk"))


@pytest.mark.parametrize("archive_schema", ["public", "demo_archive"])
def test_refuses_unregistered_inheritance_before_any_truncate(reset_ready, archive_schema):
    reset, engine = reset_ready
    archive = f'"{archive_schema}"."archive_users"'
    archive_sequence = f'{archive_schema}.archive_users_archive_id_seq'
    with Session(engine) as db:
        db.add(models.User(name="Scope sentinel", email=f"scope-{archive_schema}@example.test",
                           role="customer", is_active=True, is_banned=False))
        db.commit()
    with engine.begin() as connection:
        if archive_schema != "public":
            connection.execute(sa.text(f'CREATE SCHEMA "{archive_schema}"'))
        connection.execute(sa.text(
            f"CREATE TABLE {archive} (archive_id bigserial) INHERITS (users)"
        ))
        connection.execute(sa.text(
            f"INSERT INTO {archive} (id, name, email, role, is_active, is_banned, created_at) "
            "VALUES (90001, 'Archive sentinel', 'archive@example.test', 'customer', true, false, now())"
        ))
        connection.execute(sa.text("SELECT setval(:sequence, 73)"), {"sequence": archive_sequence})

    def rows_and_sequences(connection):
        return (
            connection.execute(sa.text("SELECT * FROM ONLY users ORDER BY id")).all(),
            connection.execute(sa.text(f"SELECT * FROM {archive} ORDER BY id")).all(),
            connection.execute(sa.text("SELECT last_value, is_called FROM users_id_seq")).one(),
            connection.execute(sa.text(
                f'SELECT last_value, is_called FROM "{archive_schema}".archive_users_archive_id_seq'
            )).one(),
        )

    truncate_attempts = []
    def record_truncate(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("TRUNCATE"):
            truncate_attempts.append(statement)
    try:
        with engine.connect() as connection:
            before = rows_and_sequences(connection)
        with Session(engine) as db:
            application_before = snapshot(db)
        sa.event.listen(engine, "before_cursor_execute", record_truncate)
        error = None
        try:
            with Session(engine) as db:
                try:
                    reset.reset_demo_database(db, "reset-workshop-demo")
                finally:
                    assert not db.in_transaction()
        except ValueError as exc:
            error = exc
        with engine.connect() as connection:
            assert rows_and_sequences(connection) == before
        with Session(engine) as db:
            assert snapshot(db) == application_before
        assert error is not None and "inheritance or partition" in str(error)
        assert truncate_attempts == []
    finally:
        sa.event.remove(engine, "before_cursor_execute", record_truncate)
        with engine.begin() as connection:
            connection.execute(sa.text(f"DROP TABLE {archive}"))
            if archive_schema != "public":
                connection.execute(sa.text(f'DROP SCHEMA "{archive_schema}"'))


@pytest.mark.parametrize("with_partition", [True, False])
def test_refuses_partitioned_application_table_before_any_truncate(reset_ready, with_partition):
    reset, engine = reset_ready
    with Session(engine) as db:
        db.add(models.User(name="Partition scope sentinel", email=f"partition-{with_partition}@example.test",
                           role="customer", is_active=True, is_banned=False))
        db.commit()
    with engine.begin() as connection:
        connection.execute(sa.text("ALTER TABLE demo_ai_usage RENAME TO original_demo_ai_usage"))
        connection.execute(sa.text(
            "CREATE TABLE demo_ai_usage (LIKE original_demo_ai_usage INCLUDING ALL) "
            "PARTITION BY RANGE (usage_date)"
        ))
        if with_partition:
            connection.execute(sa.text(
                "CREATE TABLE archive_demo_usage PARTITION OF demo_ai_usage DEFAULT"
            ))
            connection.execute(sa.text(
                "INSERT INTO demo_ai_usage VALUES ('2026-10-10', 'archive-sentinel', 3, now(), 1)"
            ))
    truncate_attempts = []
    def record_truncate(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("TRUNCATE"):
            truncate_attempts.append(statement)
    try:
        with engine.connect() as connection:
            before = connection.execute(sa.text("SELECT * FROM demo_ai_usage")).all()
            users_before = connection.execute(sa.text("SELECT * FROM users ORDER BY id")).all()
            sequence_before = connection.execute(sa.text(
                "SELECT last_value, is_called FROM users_id_seq"
            )).one()
        with Session(engine) as db:
            application_before = snapshot(db)
        sa.event.listen(engine, "before_cursor_execute", record_truncate)
        error = None
        try:
            with Session(engine) as db:
                try:
                    reset.reset_demo_database(db, "reset-workshop-demo")
                finally:
                    assert not db.in_transaction()
        except ValueError as exc:
            error = exc
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT * FROM demo_ai_usage")).all() == before
            assert connection.execute(sa.text("SELECT * FROM users ORDER BY id")).all() == users_before
            assert connection.execute(sa.text(
                "SELECT last_value, is_called FROM users_id_seq"
            )).one() == sequence_before
        with Session(engine) as db:
            assert snapshot(db) == application_before
        assert error is not None and "inheritance or partition" in str(error)
        assert truncate_attempts == []
    finally:
        sa.event.remove(engine, "before_cursor_execute", record_truncate)
        with engine.begin() as connection:
            if with_partition:
                connection.execute(sa.text("DROP TABLE archive_demo_usage"))
            connection.execute(sa.text("DROP TABLE demo_ai_usage"))
            connection.execute(sa.text("ALTER TABLE original_demo_ai_usage RENAME TO demo_ai_usage"))
