from datetime import datetime, timezone

from backend import models
from tests.conftest import register_email_code


def test_public_providers_hide_pending_profiles(client, marketplace):
    listed = client.get("/providers", params={"service_province": "Istanbul"})
    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]["items"]
    assert any(
        item["id"] == marketplace["provider_profile"]["id"] for item in items
    )


def test_customer_home_recommendations(client, marketplace):
    headers = marketplace["customer"]["headers"]
    client.post(
        "/customer/profile",
        json={
            "phone_number": "+905551110001",
            "address": "Besiktas",
            "service_province": "Istanbul",
            "latitude": 41.04,
            "longitude": 29.0,
        },
        headers=headers,
    )
    response = client.get(
        "/customer/home/recommendations",
        params={"service_province": "Istanbul", "provider_tag": "plumbing"},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def test_admin_dashboard_and_favorites(client, marketplace):
    dashboard = client.get("/admin/dashboard", headers=marketplace["admin"]["headers"])
    assert dashboard.status_code == 200, dashboard.text

    provider_id = marketplace["provider_profile"]["id"]
    customer = marketplace["customer"]["headers"]
    added = client.post(f"/customer/favorites/{provider_id}", headers=customer)
    assert added.status_code == 200, added.text
    favorites = client.get("/customer/favorites", headers=customer)
    assert favorites.status_code == 200
    assert favorites.json()["data"]["total"] == 1


def test_customer_provider_detail_exposes_open_and_favorite_state(
    client, db_session, marketplace, monkeypatch
):
    import backend.utils.availability as availability_utils
    from backend.utils.service_locations import seed_service_locations

    provider_id = marketplace["provider_profile"]["id"]
    customer_headers = marketplace["customer"]["headers"]
    locations = seed_service_locations(db_session)
    district = locations["tr-istanbul-city-kadikoy"]
    db_session.add(
        models.ProviderServiceArea(
            provider_profile_id=provider_id,
            service_location_id=district.id,
        )
    )
    db_session.commit()
    open_time = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(availability_utils, "utc_now", lambda: open_time)

    detail = client.get(
        f"/customer/providers/{provider_id}", headers=customer_headers
    )
    assert detail.status_code == 200, detail.text
    provider = detail.json()["data"]["provider"]
    assert provider["is_open"] is True
    assert provider["is_favorited"] is False
    assert provider["service_areas"] == [
        {
            "id": district.id,
            "name": "Kadikoy",
            "level": "district",
            "label": "Istanbul / Istanbul / Kadikoy",
        }
    ]

    own_profile = client.get(
        "/provider/profile", headers=marketplace["provider"]["headers"]
    )
    assert own_profile.status_code == 200, own_profile.text
    assert own_profile.json()["data"]["is_open"] is True
    assert "average_rating" in own_profile.json()["data"]
    assert "review_count" in own_profile.json()["data"]

    added = client.post(f"/customer/favorites/{provider_id}", headers=customer_headers)
    assert added.status_code == 200, added.text

    detail = client.get(
        f"/customer/providers/{provider_id}", headers=customer_headers
    )
    assert detail.json()["data"]["provider"]["is_favorited"] is True

    closed_time = datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(availability_utils, "utc_now", lambda: closed_time)
    detail = client.get(
        f"/customer/providers/{provider_id}", headers=customer_headers
    )
    assert detail.json()["data"]["provider"]["is_open"] is False


def test_customer_provider_detail_honors_unavailable_date_override(
    client, db_session, marketplace, monkeypatch
):
    import backend.utils.availability as availability_utils

    provider_id = marketplace["provider_profile"]["id"]
    db_session.add(
        models.ProviderAvailabilityOverride(
            provider_profile_id=provider_id,
            override_date="2026-10-05",
            start_time="08:00",
            end_time="20:00",
            is_available=False,
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        availability_utils,
        "utc_now",
        lambda: datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc),
    )
    detail = client.get(
        f"/customer/providers/{provider_id}",
        headers=marketplace["customer"]["headers"],
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["provider"]["is_open"] is False


def test_customer_provider_detail_favorite_state_is_customer_specific(
    client, marketplace
):
    created = client.post(
        "/register",
        json={
            "first_name": "Second",
            "last_name": "Customer",
            "email": "second-customer@example.com",
            "password": "Password123",
            "confirm_password": "Password123",
            "tos_accepted": True,
            "role": "customer",
            "email_code": register_email_code(client, "second-customer@example.com"),
        },
    )
    assert created.status_code == 200, created.text
    logged_in = client.post(
        "/login",
        data={
            "username": "second-customer@example.com",
            "password": "Password123",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert logged_in.status_code == 200, logged_in.text
    second_customer_headers = {
        "Authorization": f"Bearer {logged_in.json()['data']['access_token']}"
    }
    provider_id = marketplace["provider_profile"]["id"]

    added = client.post(
        f"/customer/favorites/{provider_id}",
        headers=marketplace["customer"]["headers"],
    )
    assert added.status_code == 200, added.text

    first_detail = client.get(
        f"/customer/providers/{provider_id}",
        headers=marketplace["customer"]["headers"],
    )
    second_detail = client.get(
        f"/customer/providers/{provider_id}",
        headers=second_customer_headers,
    )
    assert first_detail.json()["data"]["provider"]["is_favorited"] is True
    assert second_detail.json()["data"]["provider"]["is_favorited"] is False


def test_provider_dashboard_requires_provider(client, marketplace):
    denied = client.get(
        "/provider/dashboard", headers=marketplace["customer"]["headers"]
    )
    assert denied.status_code == 403
    ok = client.get("/provider/dashboard", headers=marketplace["provider"]["headers"])
    assert ok.status_code == 200
