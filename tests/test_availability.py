from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from backend import models
from backend.routers.provider import validate_availability_override_date
from backend.utils.availability import (
    is_provider_available_for_datetime_range,
    is_provider_open_now,
)


@pytest.fixture
def availability_provider_id(db_session):
    user = models.User(
        name="Availability Provider",
        email="availability-provider@example.com",
        role="provider",
        is_active=True,
        is_banned=False,
    )
    db_session.add(user)
    db_session.flush()

    profile = models.ProviderProfile(
        user_id=user.id,
        business_name="Availability Provider",
        bio="Provider for availability tests.",
        phone_number="+905551110000",
        address="Istanbul",
        service_province="Istanbul",
        latitude=41.0082,
        longitude=28.9784,
        tags="moving",
        certificate_name="Test certificate",
        certificate_url="https://example.com/certificate.pdf",
        hourly_rate=100,
        verification_status="approved",
    )
    db_session.add(profile)
    db_session.commit()
    return profile.id


def test_is_provider_open_now_uses_weekly_hours(db_session, availability_provider_id):
    db_session.add(
        models.ProviderAvailability(
            provider_profile_id=availability_provider_id,
            weekday=1,
            start_time="08:00",
            end_time="20:00",
            is_available=True,
        )
    )
    db_session.commit()

    monday_open = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)
    monday_closed = datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc)
    assert is_provider_open_now(availability_provider_id, db_session, monday_open) is True
    assert is_provider_open_now(availability_provider_id, db_session, monday_closed) is False


def test_is_provider_open_now_closes_at_istanbul_end_time(
    db_session, availability_provider_id
):
    db_session.add(
        models.ProviderAvailability(
            provider_profile_id=availability_provider_id,
            weekday=1,
            start_time="08:00",
            end_time="20:00",
            is_available=True,
        )
    )
    db_session.commit()

    exactly_at_close = datetime(2026, 10, 5, 17, 0, tzinfo=timezone.utc)
    assert is_provider_open_now(availability_provider_id, db_session, exactly_at_close) is False


def test_provider_range_uses_istanbul_for_naive_and_aware_inputs(
    db_session, availability_provider_id
):
    db_session.add(
        models.ProviderAvailability(
            provider_profile_id=availability_provider_id,
            weekday=1,
            start_time="08:00",
            end_time="20:00",
            is_available=True,
        )
    )
    db_session.commit()

    naive_local_range = (
        datetime(2026, 10, 5, 10, 0),
        datetime(2026, 10, 5, 12, 0),
    )
    aware_sydney_range = (
        datetime(2026, 10, 5, 21, 0, tzinfo=timezone(timedelta(hours=10))),
        datetime(2026, 10, 5, 23, 0, tzinfo=timezone(timedelta(hours=10))),
    )

    assert is_provider_available_for_datetime_range(
        availability_provider_id, *naive_local_range, db_session
    ) is True
    assert is_provider_available_for_datetime_range(
        availability_provider_id, *aware_sydney_range, db_session
    ) is True


def test_is_provider_open_now_gives_date_override_precedence(
    db_session, availability_provider_id
):
    db_session.add(
        models.ProviderAvailability(
            provider_profile_id=availability_provider_id,
            weekday=1,
            start_time="08:00",
            end_time="20:00",
            is_available=True,
        )
    )
    db_session.add(
        models.ProviderAvailabilityOverride(
            provider_profile_id=availability_provider_id,
            override_date="2026-10-05",
            start_time="08:00",
            end_time="20:00",
            is_available=False,
        )
    )
    db_session.commit()

    monday_override = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)
    assert is_provider_open_now(availability_provider_id, db_session, monday_override) is False


def test_is_provider_open_now_uses_istanbul_date_at_utc_midnight_boundary(
    db_session, availability_provider_id
):
    db_session.add_all(
        [
            models.ProviderAvailability(
                provider_profile_id=availability_provider_id,
                weekday=7,
                start_time="00:00",
                end_time="23:59",
                is_available=True,
            ),
            models.ProviderAvailabilityOverride(
                provider_profile_id=availability_provider_id,
                override_date="2026-10-05",
                start_time="08:00",
                end_time="20:00",
                is_available=False,
            ),
        ]
    )
    db_session.commit()

    # 22:30 UTC on Sunday is 01:30 Monday in Istanbul.
    sunday_utc = datetime(2026, 10, 4, 22, 30, tzinfo=timezone.utc)
    assert is_provider_open_now(availability_provider_id, db_session, sunday_utc) is False


def test_availability_override_date_validation_uses_istanbul_date(monkeypatch):
    import backend.routers.provider as provider_router

    current_utc = datetime(2026, 10, 4, 22, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(provider_router, "utc_now", lambda: current_utc)

    validate_availability_override_date(date(2026, 10, 5))

    with pytest.raises(HTTPException) as exc_info:
        validate_availability_override_date(date(2026, 10, 4))
    assert exc_info.value.status_code == 400
