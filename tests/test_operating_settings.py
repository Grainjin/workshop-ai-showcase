import pytest

from backend import models
from tests.conftest import register_session


@pytest.fixture
def approved_provider(client, db_session):
    provider = register_session(
        client, "settings-provider@example.com", role="provider", name="Settings Provider"
    )
    user = db_session.get(models.User, provider["user"]["id"])
    user.identity_verification_status = "approved"
    user.qualification_verification_status = "approved"
    profile = models.ProviderProfile(
        user_id=user.id,
        business_name="Settings Provider",
        bio="Original description",
        phone_number="+905551110000",
        address="Original address",
        service_province="Istanbul",
        latitude=41.0082,
        longitude=28.9784,
        business_place_id="place-original",
        tags="cleaning,plumbing",
        certificate_name="proof.pdf",
        certificate_url="/verification-files/qualification/proof.pdf",
        hourly_rate=400,
        verification_status="approved",
        identity_verification_status="approved",
        qualification_verification_status="approved",
    )
    db_session.add(profile)
    db_session.flush()
    db_session.add_all(
        [
            models.ProviderApprovedService(
                provider_profile_id=profile.id,
                service_category=category,
                is_enabled=True,
            )
            for category in ("cleaning", "plumbing")
        ]
    )
    db_session.commit()
    return provider, profile


@pytest.mark.parametrize("qualification_status", ["locked", "not_submitted", "pending", "rejected"])
def test_operating_settings_are_locked_until_qualification_approval(
    client, db_session, approved_provider, qualification_status
):
    provider, profile = approved_provider
    profile.qualification_verification_status = qualification_status
    db_session.commit()
    response = client.patch(
        "/provider/operating-settings",
        json={"hourly_rate": 500},
        headers=provider["headers"],
    )
    assert response.status_code == 403


def test_operating_settings_update_current_profile_without_changing_approval(
    client, db_session, approved_provider
):
    provider, profile = approved_provider
    response = client.patch(
        "/provider/operating-settings",
        json={
            "description": "Updated description",
            "contact_phone": "+905551110099",
            "business_address": "Kadikoy, Istanbul",
            "business_place_id": "place-current",
            "business_latitude": 40.9909,
            "business_longitude": 29.0303,
            "hourly_rate": 525,
            "enabled_service_categories": ["cleaning"],
        },
        headers=provider["headers"],
    )
    assert response.status_code == 200, response.text
    db_session.refresh(profile)
    assert profile.bio == "Updated description"
    assert profile.phone_number == "+905551110099"
    assert profile.address == "Kadikoy, Istanbul"
    assert profile.business_place_id == "place-current"
    assert profile.hourly_rate == 525
    assert profile.tags == "cleaning"
    assert profile.qualification_verification_status == "approved"


def test_operating_settings_accept_current_location_without_place_id(
    client, db_session, approved_provider
):
    provider, profile = approved_provider
    response = client.patch(
        "/provider/operating-settings",
        json={
            "business_address": "Current location",
            "business_place_id": None,
            "business_latitude": 41.015,
            "business_longitude": 28.979,
        },
        headers=provider["headers"],
    )

    assert response.status_code == 200, response.text
    db_session.refresh(profile)
    assert profile.address == "Current location"
    assert profile.business_place_id is None
    assert profile.latitude == 41.015
    assert profile.longitude == 28.979


def test_only_approved_services_can_be_enabled(client, approved_provider):
    provider, _ = approved_provider
    response = client.patch(
        "/provider/operating-settings",
        json={"enabled_service_categories": ["moving"]},
        headers=provider["headers"],
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"hourly_rate": 0},
        {"business_address": "Address only"},
        {"business_latitude": 41.0, "business_longitude": 29.0},
        {"description": None},
    ],
)
def test_operating_settings_reject_invalid_or_partial_updates(
    client, approved_provider, payload
):
    provider, _ = approved_provider
    response = client.patch(
        "/provider/operating-settings",
        json=payload,
        headers=provider["headers"],
    )
    assert response.status_code == 422


def test_new_provider_cannot_use_legacy_settings_routes(client, approved_provider):
    provider, _ = approved_provider
    old_operating = client.patch(
        "/provider/profile/operating-settings",
        json={"hourly_rate": 500},
        headers=provider["headers"],
    )
    old_contact = client.patch(
        "/provider/profile/contact",
        json={"address": "Bypass address"},
        headers=provider["headers"],
    )
    assert old_operating.status_code == 409
    assert old_contact.status_code == 409


def test_operating_settings_are_published_in_openapi(client):
    document = client.get("/openapi.json")
    assert document.status_code == 200
    assert "patch" in document.json()["paths"]["/provider/operating-settings"]
