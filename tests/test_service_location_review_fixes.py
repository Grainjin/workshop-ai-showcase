from backend import models
from backend.ai.tools import search_providers_tool
from backend.schemas.ai import AIChatRequest
from backend.utils import ai_chat_handler
from backend.utils.service_locations import seed_service_locations
from tests.conftest import register_session


def test_reference_location_seed_command_is_independent_of_demo_seed(
    db_session, monkeypatch
):
    import backend.seed_locations as seed_locations

    monkeypatch.setattr(seed_locations, "SessionLocal", lambda: db_session)

    seed_locations.main()

    assert db_session.query(models.ServiceLocation).count() == 298


def test_explicit_ai_province_does_not_fallback_to_saved_location_id(
    client, db_session
):
    seeded = seed_service_locations(db_session)
    db_session.commit()
    customer = register_session(client, "location-context@example.com")

    created = client.post(
        "/customer/profile",
        json={
            "phone_number": "+905551110002",
            "address": "Kadikoy",
            "service_province": "Istanbul",
            "service_location_id": seeded["tr-istanbul-city-kadikoy"].id,
        },
        headers=customer["headers"],
    )
    assert created.status_code == 200, created.text

    user = db_session.query(models.User).filter_by(id=customer["user"]["id"]).one()
    result = search_providers_tool(
        query="plumbing",
        service_tags=["plumbing"],
        service_province="Ankara",
        service_location_id=None,
        max_price=None,
        budget_preference=None,
        current_user=user,
        db=db_session,
    )

    assert result["resolved_need"]["service_province"] == "Ankara"
    assert result["resolved_need"]["service_location_id"] is None


def test_province_only_customer_update_clears_old_location_id(client, db_session):
    seeded = seed_service_locations(db_session)
    db_session.commit()
    customer = register_session(client, "clear-location@example.com")

    created = client.post(
        "/customer/profile",
        json={
            "phone_number": "+905551110003",
            "address": "Kadikoy",
            "service_province": "Istanbul",
            "service_location_id": seeded["tr-istanbul-city-kadikoy"].id,
        },
        headers=customer["headers"],
    )
    assert created.status_code == 200, created.text

    updated = client.put(
        "/customer/profile/service-province",
        json={"service_province": "Ankara"},
        headers=customer["headers"],
    )

    assert updated.status_code == 200, updated.text
    profile = updated.json()["data"]["profile"]
    assert profile["service_province"] == "Ankara"
    assert profile["service_location_id"] is None


def test_provider_service_area_is_separate_from_business_location(
    client, db_session, marketplace
):
    seeded = seed_service_locations(db_session)
    provider = db_session.query(models.ProviderProfile).filter_by(
        id=marketplace["provider_profile"]["id"]
    ).one()
    provider.service_province = "Istanbul"
    provider.service_location_id = seeded["tr-istanbul-city-kadikoy"].id
    db_session.commit()

    updated = client.put(
        "/provider/service-areas",
        json={"service_location_ids": [seeded["tr-ankara"].id]},
        headers=marketplace["provider"]["headers"],
    )

    assert updated.status_code == 200, updated.text
    db_session.refresh(provider)
    assert provider.service_province == "Istanbul"
    assert provider.service_location_id == seeded["tr-istanbul-city-kadikoy"].id
    areas = db_session.query(models.ProviderServiceArea).filter_by(
        provider_profile_id=provider.id
    ).all()
    assert [area.service_location_id for area in areas] == [seeded["tr-ankara"].id]


def test_location_id_filter_keeps_legacy_provider_and_is_case_insensitive(
    client, db_session, marketplace
):
    seeded = seed_service_locations(db_session)
    db_session.commit()

    by_id = client.get(
        "/providers",
        params={"service_location_id": seeded["tr-istanbul"].id},
    )
    assert by_id.status_code == 200, by_id.text
    assert marketplace["provider_profile"]["id"] in {
        item["id"] for item in by_id.json()["data"]["items"]
    }

    by_name = client.get("/providers", params={"service_province": "istanbul"})
    assert by_name.status_code == 200, by_name.text
    assert marketplace["provider_profile"]["id"] in {
        item["id"] for item in by_name.json()["data"]["items"]
    }


def test_rule_based_ai_fallback_forwards_location_id(monkeypatch, db_session, marketplace):
    captured = {}

    def fake_search_providers_tool(**kwargs):
        captured.update(kwargs)
        return {
            "resolved_need": {
                "service_tags": ["plumbing"],
                "service_province": None,
                "service_location_id": kwargs["service_location_id"],
            },
            "recommendations": [
                {
                    "provider_id": marketplace["provider_profile"]["id"],
                    "business_name": "Test Provider",
                    "service_province": "Istanbul",
                    "tags": "plumbing",
                }
            ],
            "recommendation_count": 1,
            "no_core_tag_matched": False,
        }

    monkeypatch.setattr(ai_chat_handler, "search_providers_tool", fake_search_providers_tool)
    monkeypatch.setattr(ai_chat_handler, "save_last_recommended_providers", lambda *args: None)
    monkeypatch.setattr(
        ai_chat_handler,
        "save_last_provider_recommendation_context",
        lambda *args: None,
    )
    monkeypatch.setattr(
        ai_chat_handler,
        "save_tool_calling_exchange",
        lambda request_data, current_user, response, request_metadata, db: response,
    )

    user = db_session.query(models.User).filter_by(id=marketplace["customer"]["user"]["id"]).one()
    request_data = AIChatRequest(message="Find a plumber", service_location_id=123)

    ai_chat_handler.handle_rule_based_chat_fallback(
        request_data,
        user,
        {},
        db_session,
    )

    assert captured["service_location_id"] == 123
