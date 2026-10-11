import pytest
from pydantic import ValidationError

from backend import models
from backend.schemas.provider_verification import QualificationVerificationSubmit
from backend.utils.service_locations import seed_service_locations
from tests.conftest import create_admin_session, register_session
from tests.test_provider_verification_flow import (
    approve_identity,
    submit_identity,
    upload_qualification_file,
)


def organisation_payload(file):
    return {
        "entity_type": "organisation",
        "legal_name": "Istanbul Services AS",
        "unique_enterprise_id": "tr-123456",
        "description": "Qualified organisation services",
        "contact_phone": "+905551110000",
        "business_address": "Kadikoy, Istanbul",
        "business_place_id": "place-org",
        "business_latitude": 40.9909,
        "business_longitude": 29.0303,
        "service_categories": ["cleaning"],
        "service_location_ids": [1],
        "qualification_files": [file],
    }


def test_organisation_requires_legal_name_and_unique_enterprise_id():
    with pytest.raises(ValidationError):
        QualificationVerificationSubmit(
            **{
                **organisation_payload(
                    {
                        "file_url": "/verification-files/qualification/proof.pdf",
                        "original_file_name": "proof.pdf",
                        "content_type": "application/pdf",
                    }
                ),
                "legal_name": None,
                "unique_enterprise_id": None,
            }
        )


def test_personal_provider_cannot_submit_organisation_identity_fields():
    payload = organisation_payload(
        {
            "file_url": "/verification-files/qualification/proof.pdf",
            "original_file_name": "proof.pdf",
            "content_type": "application/pdf",
        }
    )
    payload["entity_type"] = "personal"
    with pytest.raises(ValidationError):
        QualificationVerificationSubmit(**payload)


def test_new_provider_cannot_use_legacy_profile_or_review_endpoints(client, db_session):
    provider = register_session(
        client, "no-bypass@example.com", role="provider", name="No Bypass"
    )
    admin = create_admin_session(client, db_session, email="no-bypass-admin@example.com")
    legacy_profile = client.post(
        "/provider/profile",
        json={
            "business_name": "Bypass",
            "bio": "Should not be accepted",
            "phone_number": "+905551110000",
            "address": "Istanbul",
            "service_province": "Istanbul",
            "tags": ["cleaning"],
            "certificate_name": "proof",
            "certificate_url": "https://example.com/proof.pdf",
            "hourly_rate": 100,
        },
        headers=provider["headers"],
    )
    assert legacy_profile.status_code == 409

    profile = models.ProviderProfile(
        user_id=provider["user"]["id"],
        business_name="Legacy-shaped profile",
        bio="Test",
        phone_number="+905551110000",
        address="Istanbul",
        service_province="Istanbul",
        tags="cleaning",
        certificate_name="proof",
        certificate_url="https://example.com/proof.pdf",
        hourly_rate=100,
    )
    db_session.add(profile)
    db_session.commit()
    legacy_review = client.put(
        f"/admin/providers/{profile.id}/verification",
        json={"verification_status": "approved", "verification_note": "bypass"},
        headers=admin["headers"],
    )
    assert legacy_review.status_code == 409


def test_organisation_approval_uses_legal_name_and_persists_enterprise_id(
    client, db_session
):
    provider = register_session(
        client, "organisation@example.com", role="provider", name="Org Owner"
    )
    admin = create_admin_session(client, db_session, email="organisation-admin@example.com")
    identity_id = submit_identity(client, provider["headers"]).json()["data"]["id"]
    assert approve_identity(client, admin["headers"], identity_id).status_code == 200
    file = upload_qualification_file(client, provider["headers"])
    seeded = seed_service_locations(db_session)
    db_session.commit()
    payload = organisation_payload(file)
    payload["service_location_ids"] = [seeded["tr-istanbul"].id]
    submitted = client.post(
        "/provider/qualification-verification",
        json=payload,
        headers=provider["headers"],
    )
    assert submitted.status_code == 200, submitted.text
    application = submitted.json()["data"]
    assert application["display_name"] == "Istanbul Services AS"
    assert application["unique_enterprise_id"] == "TR-123456"

    approved = client.put(
        f"/admin/qualification-verifications/{application['id']}/decision",
        json={"status": "approved"},
        headers=admin["headers"],
    )
    assert approved.status_code == 200, approved.text
    profile = db_session.get(
        models.ProviderProfile, approved.json()["data"]["provider_profile_id"]
    )
    assert profile.business_name == "Istanbul Services AS"
    assert profile.unique_enterprise_id == "TR-123456"


def test_reviewed_application_cannot_be_reviewed_twice(client, db_session):
    provider = register_session(
        client, "single-review@example.com", role="provider", name="Single Review"
    )
    admin = create_admin_session(client, db_session, email="single-review-admin@example.com")
    application_id = submit_identity(client, provider["headers"]).json()["data"]["id"]
    assert approve_identity(client, admin["headers"], application_id).status_code == 200
    repeated = approve_identity(client, admin["headers"], application_id)
    assert repeated.status_code == 409
