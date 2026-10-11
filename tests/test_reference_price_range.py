from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend import models
from backend.core.clock import utc_now
from backend.utils.reference_price import calculate_reference_price_range
from tests.conftest import create_booking


NO_HISTORY = {
    "has_history": False,
    "minimum": None,
    "maximum": None,
    "currency": "TRY",
    "sample_count": 0,
}


def _booking(
    db_session,
    marketplace,
    *,
    service_category: str | None = "plumbing",
) -> models.Booking:
    booking = models.Booking(
        customer_id=marketplace["customer"]["user"]["id"],
        provider_profile_id=marketplace["provider_profile"]["id"],
        title="Reference price booking",
        service_category=service_category,
        service_description="Repair",
        service_address="Istanbul",
        service_latitude=41.0,
        service_longitude=29.0,
        scheduled_start_time=datetime(2026, 10, 5, 10, tzinfo=timezone.utc),
        scheduled_end_time=datetime(2026, 10, 5, 12, tzinfo=timezone.utc),
        total_amount=Decimal("0.00"),
        status="pending",
    )
    db_session.add(booking)
    db_session.flush()
    return booking


def _revision(
    db_session,
    marketplace,
    booking: models.Booking,
    amount: str,
    revision_number: int = 1,
    *,
    visit_fee: str | None = None,
    declined: bool = False,
) -> models.BookingQuoteRevision:
    revision = models.BookingQuoteRevision(
        booking_id=booking.id,
        revision_number=revision_number,
        quote_amount=Decimal(amount),
        expected_service_amount=Decimal(amount),
        visit_fee_amount=Decimal(visit_fee) if visit_fee is not None else None,
        created_by_user_id=marketplace["provider"]["user"]["id"],
        declined_at=utc_now() if declined else None,
        created_at=utc_now() + timedelta(seconds=revision_number),
    )
    db_session.add(revision)
    db_session.flush()
    return revision


def test_reference_range_has_no_history_for_zero_matches(db_session, marketplace):
    current = _booking(db_session, marketplace)

    assert calculate_reference_price_range(current, db_session) == NO_HISTORY


def test_reference_range_uses_one_historical_booking(db_session, marketplace):
    current = _booking(db_session, marketplace)
    historical = _booking(db_session, marketplace)
    _revision(db_session, marketplace, historical, "1000")

    assert calculate_reference_price_range(current, db_session) == {
        "has_history": True,
        "minimum": 900,
        "maximum": 1100,
        "currency": "TRY",
        "sample_count": 1,
    }


def test_reference_range_averages_multiple_historical_bookings(
    db_session, marketplace
):
    current = _booking(db_session, marketplace)
    first = _booking(db_session, marketplace)
    second = _booking(db_session, marketplace)
    _revision(db_session, marketplace, first, "1000")
    _revision(db_session, marketplace, second, "2000")

    result = calculate_reference_price_range(current, db_session)

    assert result["minimum"] == 1350
    assert result["maximum"] == 1650
    assert result["sample_count"] == 2


def test_reference_range_rounds_half_up(db_session, marketplace):
    current = _booking(db_session, marketplace)
    historical = _booking(db_session, marketplace)
    _revision(db_session, marketplace, historical, "5")

    result = calculate_reference_price_range(current, db_session)

    assert result["minimum"] == 5
    assert result["maximum"] == 6


def test_reference_range_excludes_other_service_categories(db_session, marketplace):
    current = _booking(db_session, marketplace)
    historical = _booking(db_session, marketplace, service_category="cleaning")
    _revision(db_session, marketplace, historical, "1000")

    assert calculate_reference_price_range(current, db_session) == NO_HISTORY


def test_reference_range_excludes_current_booking_entirely(db_session, marketplace):
    current = _booking(db_session, marketplace)
    _revision(db_session, marketplace, current, "1000", 1)
    _revision(db_session, marketplace, current, "1200", 2)

    assert calculate_reference_price_range(current, db_session) == NO_HISTORY


def test_reference_range_uses_only_latest_revision_per_booking(
    db_session, marketplace
):
    current = _booking(db_session, marketplace)
    historical = _booking(db_session, marketplace)
    _revision(db_session, marketplace, historical, "1000", 1)
    _revision(db_session, marketplace, historical, "1200", 2)

    assert calculate_reference_price_range(current, db_session) == {
        "has_history": True,
        "minimum": 1080,
        "maximum": 1320,
        "currency": "TRY",
        "sample_count": 1,
    }


def test_reference_range_latest_declined_revision_still_counts(
    db_session, marketplace
):
    current = _booking(db_session, marketplace)
    historical = _booking(db_session, marketplace)
    _revision(db_session, marketplace, historical, "1000", 1)
    _revision(db_session, marketplace, historical, "1500", 2, declined=True)

    result = calculate_reference_price_range(current, db_session)

    assert result["minimum"] == 1350
    assert result["maximum"] == 1650
    assert result["sample_count"] == 1


def test_reference_range_ignores_visit_fee(db_session, marketplace):
    current = _booking(db_session, marketplace)
    historical = _booking(db_session, marketplace)
    _revision(db_session, marketplace, historical, "1000", visit_fee="900")

    result = calculate_reference_price_range(current, db_session)

    assert result["minimum"] == 900
    assert result["maximum"] == 1100


def test_reference_range_has_no_history_for_legacy_booking(db_session, marketplace):
    current = _booking(db_session, marketplace, service_category=None)
    historical = _booking(db_session, marketplace)
    _revision(db_session, marketplace, historical, "1000")

    assert calculate_reference_price_range(current, db_session) == NO_HISTORY


def test_booking_detail_exposes_shared_reference_range_to_customer_and_provider(
    client, db_session, marketplace
):
    historical = _booking(db_session, marketplace)
    _revision(db_session, marketplace, historical, "1000")
    db_session.commit()
    current = create_booking(
        client,
        marketplace["customer"]["headers"],
        marketplace["provider_profile"]["id"],
    )

    customer_response = client.get(
        f"/bookings/{current['id']}", headers=marketplace["customer"]["headers"]
    )
    provider_response = client.get(
        f"/bookings/{current['id']}", headers=marketplace["provider"]["headers"]
    )

    assert customer_response.status_code == 200, customer_response.text
    assert provider_response.status_code == 200, provider_response.text
    customer_range = customer_response.json()["data"]["reference_price_range"]
    assert customer_range == provider_response.json()["data"]["reference_price_range"]
    assert customer_range["sample_count"] == 1


def test_booking_lists_do_not_serialize_reference_price_range(client, marketplace):
    create_booking(
        client,
        marketplace["customer"]["headers"],
        marketplace["provider_profile"]["id"],
    )

    customer_list = client.get(
        "/customer/bookings", headers=marketplace["customer"]["headers"]
    )
    provider_list = client.get(
        "/provider/bookings", headers=marketplace["provider"]["headers"]
    )

    assert customer_list.status_code == 200, customer_list.text
    assert provider_list.status_code == 200, provider_list.text
    assert "reference_price_range" not in customer_list.json()["data"]["items"][0]
    assert "reference_price_range" not in provider_list.json()["data"]["items"][0]
