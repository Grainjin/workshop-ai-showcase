from datetime import datetime, timezone
from decimal import Decimal

from backend import models


def _booking_payload(provider_profile_id: int, service_category: str) -> dict[str, str]:
    return {
        "provider_profile_id": str(provider_profile_id),
        "service_category": service_category,
        "title": "Kitchen pipe repair",
        "service_description": "Kitchen pipe leak",
        "service_address": "Sultanahmet, Istanbul",
        "service_latitude": "41.0082",
        "service_longitude": "28.9784",
        "scheduled_start_time": "2026-10-05T10:00:00+00:00",
        "scheduled_end_time": "2026-10-05T12:00:00+00:00",
    }


def test_booking_creation_persists_enabled_canonical_service(client, marketplace):
    response = client.post(
        "/bookings",
        data=_booking_payload(marketplace["provider_profile"]["id"], "plumbing"),
        headers=marketplace["customer"]["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["booking"]["service_category"] == "plumbing"


def test_booking_creation_rejects_display_label(client, marketplace):
    response = client.post(
        "/bookings",
        data=_booking_payload(marketplace["provider_profile"]["id"], "Plumbing"),
        headers=marketplace["customer"]["headers"],
    )

    assert response.status_code == 422, response.text


def test_booking_creation_rejects_disabled_service(
    client, marketplace, db_session
):
    service = (
        db_session.query(models.ProviderApprovedService)
        .filter(
            models.ProviderApprovedService.provider_profile_id
            == marketplace["provider_profile"]["id"],
            models.ProviderApprovedService.service_category == "plumbing",
        )
        .one()
    )
    service.is_enabled = False
    db_session.commit()

    response = client.post(
        "/bookings",
        data=_booking_payload(marketplace["provider_profile"]["id"], "plumbing"),
        headers=marketplace["customer"]["headers"],
    )

    assert response.status_code == 422, response.text


def test_existing_booking_can_have_null_service_category(db_session, marketplace):
    booking = models.Booking(
        customer_id=marketplace["customer"]["user"]["id"],
        provider_profile_id=marketplace["provider_profile"]["id"],
        title="Legacy booking",
        service_description="Legacy service",
        service_address="Istanbul",
        service_latitude=41.0,
        service_longitude=29.0,
        scheduled_start_time=datetime(2026, 10, 5, 10, tzinfo=timezone.utc),
        scheduled_end_time=datetime(2026, 10, 5, 12, tzinfo=timezone.utc),
        total_amount=Decimal("0.00"),
        status="pending",
    )
    db_session.add(booking)
    db_session.commit()

    assert booking.service_category is None
