from tests.conftest import register_session


def test_patch_me_updates_name_only(client):
    customer = register_session(
        client,
        "patch-me@example.com",
        role="customer",
        name="Original Name",
    )

    response = client.patch(
        "/me",
        json={"name": "Updated Name"},
        headers=customer["headers"],
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["name"] == "Updated Name"
    assert response.json()["data"]["email"] == "patch-me@example.com"


def test_customer_profile_patch_leaves_omitted_fields_unchanged(client):
    customer = register_session(client, "customer-patch@example.com", role="customer")
    created = client.post(
        "/customer/profile",
        json={
            "phone_number": "+905551112233",
            "address": "1 Demo Street",
            "service_province": "Istanbul",
            "latitude": 41.0082,
            "longitude": 28.9784,
        },
        headers=customer["headers"],
    )
    assert created.status_code == 200, created.text

    response = client.patch(
        "/customer/profile",
        json={"address": "2 Demo Street"},
        headers=customer["headers"],
    )

    assert response.status_code == 200, response.text
    profile = response.json()["data"]["profile"]
    assert profile["address"] == "2 Demo Street"
    assert profile["phone_number"] == "+905551112233"
    assert profile["service_province"] == "Istanbul"


def test_provider_operating_patch_leaves_omitted_fields_unchanged(
    client, db_session, marketplace
):
    provider = marketplace["provider"]

    response = client.patch(
        "/provider/operating-settings",
        json={"contact_phone": "+905559998877"},
        headers=provider["headers"],
    )

    assert response.status_code == 200, response.text
    from backend import models

    profile = db_session.get(models.ProviderProfile, marketplace["provider_profile"]["id"])
    assert profile.phone_number == "+905559998877"
    assert profile.address == "Karakoy, Istanbul"
    assert profile.service_province == "Istanbul"
