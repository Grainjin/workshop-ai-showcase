from datetime import datetime, timezone

from backend import models
from backend.core.clock import utc_now


def add_approved_provider(
    db_session,
    *,
    email,
    business_name,
    tags,
    latitude,
    longitude,
    hourly_rate=500,
):
    user = models.User(
        name=business_name,
        email=email,
        role="provider",
        is_active=True,
        is_banned=False,
        created_at=utc_now(),
    )
    db_session.add(user)
    db_session.flush()
    profile = models.ProviderProfile(
        user_id=user.id,
        business_name=business_name,
        bio=f"{business_name} services",
        phone_number="+905551110099",
        address="Istanbul",
        service_province="Istanbul",
        latitude=latitude,
        longitude=longitude,
        tags=tags,
        certificate_name="Trade license",
        certificate_url="https://example.com/cert.pdf",
        hourly_rate=hourly_rate,
        verification_status="approved",
        identity_verification_status="approved",
        qualification_verification_status="approved",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def customer_search(client, headers, **params):
    response = client.get(
        "/customer/providers/search",
        params={"keyword": "plumbing", "service_province": "Istanbul", **params},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


def test_customer_search_does_not_hard_filter_saved_profile_location(
    client, marketplace
):
    profile = client.post(
        "/customer/profile",
        json={
            "phone_number": "+905551110001",
            "address": "Far saved address",
            "service_province": "Istanbul",
            "latitude": 40.0,
            "longitude": 29.0,
        },
        headers=marketplace["customer"]["headers"],
    )
    assert profile.status_code == 200, profile.text

    items = customer_search(client, marketplace["customer"]["headers"])

    assert any(
        item["id"] == marketplace["provider_profile"]["id"] for item in items
    )


def test_customer_search_filters_rating_and_open_state(
    client, marketplace, monkeypatch
):
    import backend.utils.availability as availability_utils
    import backend.utils.provider_search as provider_search_utils

    headers = marketplace["customer"]["headers"]
    monkeypatch.setattr(
        provider_search_utils,
        "get_provider_rating_summary",
        lambda provider_id, db: {"average_rating": 4.5, "review_count": 1},
    )
    rated_items = customer_search(client, headers, min_rating=4)
    assert any(
        item["id"] == marketplace["provider_profile"]["id"]
        for item in rated_items
    )

    open_time = datetime(2026, 10, 5, 7, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(availability_utils, "utc_now", lambda: open_time)
    open_items = customer_search(client, headers, is_open=True)
    assert any(
        item["id"] == marketplace["provider_profile"]["id"]
        for item in open_items
    )


def test_customer_search_sorts_nearest_and_ranks_before_limit(
    client, db_session, marketplace
):
    far_profile = add_approved_provider(
        db_session,
        email="far-provider@example.com",
        business_name="Plumbing Name Match",
        tags="other",
        latitude=41.3,
        longitude=28.0,
    )
    nearest_items = customer_search(
        client,
        marketplace["customer"]["headers"],
        latitude=41.0255,
        longitude=28.9744,
        sort_by="nearest",
    )
    assert nearest_items[0]["id"] == marketplace["provider_profile"]["id"]
    assert any(item["id"] == far_profile.id for item in nearest_items)

    ranked_items = customer_search(
        client,
        marketplace["customer"]["headers"],
        limit=1,
    )
    assert ranked_items[0]["id"] == marketplace["provider_profile"]["id"]
