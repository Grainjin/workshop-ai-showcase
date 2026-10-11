from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from datetime import datetime, timezone
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend import models
from test_onboarding_pause_migration import (
    fresh_migrated_postgresql,  # noqa: F401
    isolated_postgresql_migrations,  # noqa: F401
)


def booking_migration_columns():
    path = Path(__file__).resolve().parents[1] / "migrations/contracts/booking_columns.json"
    assert path.is_file(), "Booking requires a migration-owned, literal schema manifest"
    manifest = json.loads(path.read_text())
    config = Config(str(path.parents[2] / "alembic.ini"))
    assert manifest["revision"] == ScriptDirectory.from_config(config).get_current_head(), (
        "Migration head changed without an explicitly reviewed Booking schema manifest"
    )
    assert len(manifest["columns"]) == len(set(manifest["columns"])), "Duplicate manifest column"
    return set(manifest["columns"])


def test_booking_model_matches_migration_owned_manifest():
    assert {column.name for column in models.Booking.__table__.columns} == booking_migration_columns(), (
        "Booking model changed without an explicitly updated migration-owned schema manifest"
    )


def test_migrated_database_contains_every_booking_model_column(fresh_migrated_postgresql):
    engine, alembic_config = fresh_migrated_postgresql
    model_columns = {column.name for column in models.Booking.__table__.columns}
    with engine.connect() as connection:
        migrated_columns = {
            column["name"] for column in sa.inspect(connection).get_columns("bookings")
        }
        assert model_columns == migrated_columns == booking_migration_columns()

    assert len(ScriptDirectory.from_config(alembic_config).get_heads()) == 1
    command.downgrade(alembic_config, "-1")
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        restored_columns = {
            column["name"] for column in sa.inspect(connection).get_columns("bookings")
        }
        assert model_columns == restored_columns == booking_migration_columns()


@pytest.fixture
def migrated_booking_api(fresh_migrated_postgresql, monkeypatch):
    from backend.auth import create_access_token, get_db
    from backend.database import Base
    from backend.main import app

    engine, _ = fresh_migrated_postgresql

    def forbid_model_schema(*args, **kwargs):
        raise AssertionError("API smoke must use the Alembic schema without recreating tables")

    monkeypatch.setattr(Base.metadata, "create_all", forbid_model_schema)
    monkeypatch.setattr(Base.metadata, "drop_all", forbid_model_schema)
    monkeypatch.setattr("backend.utils.formatters.is_user_online", lambda *_: False)
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    with Session(engine) as db:
        users = {
            role: models.User(name=role.title(), email=f"{role}@migration.example", role=role,
                              email_verified_at=now)
            for role in ("customer", "provider", "admin")
        }
        outsider = models.User(name="Other Customer", email="other@migration.example", role="customer", email_verified_at=now)
        db.add_all([*users.values(), outsider])
        db.flush()
        profile = models.ProviderProfile(
            user_id=users["provider"].id, business_name="Migration Provider", bio="Plumbing",
            service_province="Istanbul", tags="plumbing", certificate_name="License",
            certificate_url="https://example.test/license", hourly_rate=100,
            identity_verification_status="approved", qualification_verification_status="approved",
        )
        db.add(profile)
        db.flush()
        booking = models.Booking(
            customer_id=users["customer"].id, provider_profile_id=profile.id,
            title="Migrated booking", service_description="Repair", service_address="Istanbul",
            service_latitude=41.0, service_longitude=29.0,
            scheduled_start_time=now, scheduled_end_time=now, total_amount=40,
            onboarding_paused=True, onboarding_pause_reason="qualification_review",
            onboarding_paused_at=now,
        )
        db.add(booking)
        db.commit()
        booking_id = booking.id
        headers = {role: {"Authorization": "Bearer " + create_access_token({"sub": str(user.id)})}
                   for role, user in {**users, "outsider": outsider}.items()}

    def migrated_db():
        with Session(engine) as db:
            yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = migrated_db
    try:
        with TestClient(app) as api:
            yield api, headers, booking_id
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


@pytest.mark.parametrize("role", ["customer", "provider", "admin"])
def test_booking_api_roles_read_alembic_migrated_schema(migrated_booking_api, role):
    api, headers, booking_id = migrated_booking_api
    response = api.get(f"/{role}/bookings", headers=headers[role])
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert [item["id"] for item in items] == [booking_id]
    assert items[0]["title"] == "Migrated booking"
    wrong_role = "provider" if role == "customer" else "customer"
    assert api.get(f"/{role}/bookings", headers=headers[wrong_role]).status_code == 403
    assert api.get(f"/{role}/bookings").status_code == 401
    if role == "customer":
        assert api.get("/customer/bookings", headers=headers["outsider"]).json()["data"]["items"] == []
