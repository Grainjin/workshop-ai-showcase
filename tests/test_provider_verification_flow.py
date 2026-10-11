from backend import models
from backend.utils.service_locations import seed_service_locations
from tests.conftest import PNG_BYTES, create_admin_session, register_session


def submit_identity(client, headers, *, document_type="national_id"):
    return client.post(
        "/provider/identity-verification",
        data={"date_of_birth": "1990-01-02", "document_type": document_type},
        files=[("files", ("identity.png", PNG_BYTES, "image/png"))],
        headers=headers,
    )


def approve_identity(client, admin_headers, application_id):
    return client.put(
        f"/admin/identity-verifications/{application_id}/decision",
        json={"status": "approved", "review_note": "Identity checked"},
        headers=admin_headers,
    )


def upload_qualification_file(client, headers):
    response = client.post(
        "/provider/qualification-files/upload",
        files=[("files", ("license.pdf", b"qualification", "application/pdf"))],
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["files"][0]


def submit_personal_qualification(client, headers, db_session, *, service_location_ids=None):
    seeded = seed_service_locations(db_session)
    db_session.commit()
    if service_location_ids is None:
        service_location_ids = [seeded["tr-istanbul"].id]
    file = upload_qualification_file(client, headers)
    return client.post(
        "/provider/qualification-verification",
        json={
            "entity_type": "personal",
            "description": "Qualified home services",
            "contact_phone": "+905551110000",
            "business_address": "Kadikoy, Istanbul",
            "business_place_id": "place-123",
            "business_latitude": 40.9909,
            "business_longitude": 29.0303,
            "service_categories": ["cleaning", "plumbing"],
            "service_location_ids": service_location_ids,
            "qualification_files": [file],
        },
        headers=headers,
    )


def test_provider_registration_starts_unverified_and_unqualified(client):
    provider = register_session(
        client, "new-provider@example.com", role="provider", name="Ada Provider"
    )
    user = provider["user"]
    assert user["identity_verification_status"] == "not_submitted"
    assert user["qualification_verification_status"] == "not_submitted"
    status = client.get("/provider/verification-status", headers=provider["headers"])
    assert status.status_code == 200
    assert status.json()["data"]["identity_status"] == "not_submitted"
    assert status.json()["data"]["qualification_status"] == "not_submitted"


def test_identity_date_of_birth_requires_exact_valid_iso_date(client):
    invalid_values = ["02-01-1990", "1990/01/02", "1990-02-30"]
    for index, value in enumerate(invalid_values):
        provider = register_session(
            client,
            f"invalid-birth-date-{index}@example.com",
            role="provider",
            name="Ada Provider",
        )
        response = client.post(
            "/provider/identity-verification",
            data={"date_of_birth": value, "document_type": "passport"},
            files=[("files", ("identity.png", PNG_BYTES, "image/png"))],
            headers=provider["headers"],
        )
        assert response.status_code == 422
        assert "date_of_birth" in response.text


def test_identity_submission_snapshots_name_and_locks_name_changes(client, db_session):
    provider = register_session(
        client, "identity-provider@example.com", role="provider", name="Ada Provider"
    )
    response = submit_identity(client, provider["headers"], document_type="passport")
    assert response.status_code == 200, response.text
    application = response.json()["data"]
    assert application["submitted_first_name"] == "Ada"
    assert application["submitted_last_name"] == "Provider"
    assert application["document_type"] == "passport"
    assert len(application["document_files"]) == 1
    document_url = application["document_files"][0]["file_url"]
    assert document_url.startswith("/verification-files/identity/")
    assert client.get(document_url, headers=provider["headers"]).status_code == 200
    customer = register_session(client, "identity-customer@example.com")
    assert client.get(document_url, headers=customer["headers"]).status_code == 403

    locked = client.patch(
        "/me", json={"first_name": "Changed"}, headers=provider["headers"]
    )
    assert locked.status_code == 409
    duplicate = submit_identity(client, provider["headers"])
    assert duplicate.status_code == 409


def test_rejected_identity_unlocks_name_and_requires_rejection_note(client, db_session):
    provider = register_session(
        client, "rejected-provider@example.com", role="provider", name="Ada Provider"
    )
    admin = create_admin_session(client, db_session, email="identity-admin@example.com")
    application_id = submit_identity(client, provider["headers"]).json()["data"]["id"]
    missing_note = client.put(
        f"/admin/identity-verifications/{application_id}/decision",
        json={"status": "rejected"},
        headers=admin["headers"],
    )
    assert missing_note.status_code == 422
    rejected = client.put(
        f"/admin/identity-verifications/{application_id}/decision",
        json={"status": "rejected", "review_note": "Document unreadable"},
        headers=admin["headers"],
    )
    assert rejected.status_code == 200
    changed = client.patch(
        "/me", json={"first_name": "Aylin"}, headers=provider["headers"]
    )
    assert changed.status_code == 200


def test_qualification_can_be_submitted_independently_and_is_immutable_while_pending(
    client, db_session
):
    provider = register_session(
        client, "qualification-provider@example.com", role="provider", name="Ada Provider"
    )
    upload = client.post(
        "/provider/qualification-files/upload",
        files=[("files", ("license.pdf", b"qualification", "application/pdf"))],
        headers=provider["headers"],
    )
    assert upload.status_code == 200, upload.text

    submitted = submit_personal_qualification(client, provider["headers"], db_session)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["display_name"] == "Ada Provider"
    locked_upload = client.post(
        "/provider/qualification-files/upload",
        files=[("files", ("replacement.pdf", b"replacement", "application/pdf"))],
        headers=provider["headers"],
    )
    assert locked_upload.status_code == 409


def test_qualification_approval_creates_profile_and_operating_settings(client, db_session):
    provider = register_session(
        client, "approved-provider@example.com", role="provider", name="Ada Provider"
    )
    admin = create_admin_session(client, db_session, email="approval-admin@example.com")
    identity_id = submit_identity(client, provider["headers"]).json()["data"]["id"]
    approve_identity(client, admin["headers"], identity_id)
    seeded = seed_service_locations(db_session)
    db_session.commit()
    application_area = seeded["tr-istanbul-city-kadikoy"]
    qualification = submit_personal_qualification(
        client,
        provider["headers"],
        db_session,
        service_location_ids=[application_area.id],
    )
    assert qualification.json()["data"]["service_location_ids"] == [application_area.id]
    assert qualification.json()["data"]["service_areas"][0]["label"] == (
        "Istanbul / Istanbul / Kadikoy"
    )
    qualification_id = qualification.json()["data"]["id"]
    decision = client.put(
        f"/admin/qualification-verifications/{qualification_id}/decision",
        json={"status": "approved", "review_note": "Qualifications checked"},
        headers=admin["headers"],
    )
    assert decision.status_code == 200, decision.text
    profile_id = decision.json()["data"]["provider_profile_id"]
    profile = db_session.get(models.ProviderProfile, profile_id)
    assert profile.business_name == "Ada Provider"
    assert profile.address == "Kadikoy, Istanbul"
    assert profile.qualification_verification_status == "approved"
    approved_areas = client.get("/provider/service-areas", headers=provider["headers"])
    assert approved_areas.status_code == 200, approved_areas.text
    assert [area["id"] for area in approved_areas.json()["data"]["service_areas"]] == [
        application_area.id
    ]

    public = client.get(f"/providers/{profile_id}")
    assert public.status_code == 200, public.text
    assert public.json()["data"]["certificate_url"] == ""
    assert public.json()["data"]["certificate_files"] == []

    services = client.get("/provider/approved-services", headers=provider["headers"])
    assert services.json()["data"]["approved_service_categories"] == [
        "cleaning",
        "plumbing",
    ]
    invalid = client.patch(
        "/provider/operating-settings",
        json={"enabled_service_categories": ["moving"]},
        headers=provider["headers"],
    )
    assert invalid.status_code == 422
    updated = client.patch(
        "/provider/operating-settings",
        json={
            "hourly_rate": 600,
            "description": "Updated description",
            "enabled_service_categories": ["cleaning"],
        },
        headers=provider["headers"],
    )
    assert updated.status_code == 200, updated.text
    db_session.refresh(profile)
    assert profile.hourly_rate == 600
    assert profile.bio == "Updated description"


def test_service_areas_accept_any_level_and_reject_overlap(client, db_session):
    provider = register_session(
        client, "areas-provider@example.com", role="provider", name="Ada Provider"
    )
    admin = create_admin_session(client, db_session, email="areas-admin@example.com")
    identity_id = submit_identity(client, provider["headers"]).json()["data"]["id"]
    approve_identity(client, admin["headers"], identity_id)
    seeded = seed_service_locations(db_session)
    db_session.commit()
    province = seeded["tr-istanbul"]
    district = seeded["tr-istanbul-city-kadikoy"]
    qualification_id = submit_personal_qualification(
        client,
        provider["headers"],
        db_session,
        service_location_ids=[province.id],
    ).json()["data"]["id"]
    client.put(
        f"/admin/qualification-verifications/{qualification_id}/decision",
        json={"status": "approved"},
        headers=admin["headers"],
    )
    initial = client.get("/provider/service-areas", headers=provider["headers"])
    assert [area["id"] for area in initial.json()["data"]["service_areas"]] == [
        province.id
    ]
    province_only = client.put(
        "/provider/service-areas",
        json={"service_location_ids": [province.id]},
        headers=provider["headers"],
    )
    assert province_only.status_code == 200, province_only.text
    saved = client.get("/provider/service-areas", headers=provider["headers"])
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["service_areas"] == [
        {
            "id": province.id,
            "name": province.name,
            "level": "province",
            "label": "Istanbul",
        }
    ]
    overlap = client.put(
        "/provider/service-areas",
        json={"service_location_ids": [province.id, district.id]},
        headers=provider["headers"],
    )
    assert overlap.status_code == 422

    district_only = client.put(
        "/provider/service-areas",
        json={"service_location_ids": [district.id]},
        headers=provider["headers"],
    )
    assert district_only.status_code == 200, district_only.text
    assert district_only.json()["data"]["service_areas"] == [
        {
            "id": district.id,
            "name": "Kadikoy",
            "level": "district",
            "label": "Istanbul / Istanbul / Kadikoy",
        }
    ]
    saved_district = client.get("/provider/service-areas", headers=provider["headers"])
    assert saved_district.status_code == 200, saved_district.text
    assert saved_district.json()["data"]["service_areas"] == [
        {
            "id": district.id,
            "name": "Kadikoy",
            "level": "district",
            "label": "Istanbul / Istanbul / Kadikoy",
        }
    ]
    application = client.get(
        "/provider/qualification-verification", headers=provider["headers"]
    )
    assert application.json()["data"]["service_location_ids"] == [province.id]


def test_qualification_rejects_empty_invalid_and_overlapping_service_areas(
    client, db_session
):
    provider = register_session(
        client, "invalid-areas-provider@example.com", role="provider", name="Ada Provider"
    )
    admin = create_admin_session(client, db_session, email="invalid-areas-admin@example.com")
    identity_id = submit_identity(client, provider["headers"]).json()["data"]["id"]
    approve_identity(client, admin["headers"], identity_id)
    seeded = seed_service_locations(db_session)
    db_session.commit()
    file = upload_qualification_file(client, provider["headers"])
    base_payload = {
        "entity_type": "personal",
        "description": "Qualified home services",
        "contact_phone": "+905551110000",
        "business_address": "Kadikoy, Istanbul",
        "business_place_id": "place-123",
        "business_latitude": 40.9909,
        "business_longitude": 29.0303,
        "service_categories": ["cleaning"],
        "qualification_files": [file],
    }
    empty = client.post(
        "/provider/qualification-verification",
        json={**base_payload, "service_location_ids": []},
        headers=provider["headers"],
    )
    assert empty.status_code == 422
    missing = client.post(
        "/provider/qualification-verification",
        json={**base_payload, "service_location_ids": [999999]},
        headers=provider["headers"],
    )
    assert missing.status_code == 404
    overlap = client.post(
        "/provider/qualification-verification",
        json={
            **base_payload,
            "service_location_ids": [
                seeded["tr-istanbul"].id,
                seeded["tr-istanbul-city-kadikoy"].id,
            ],
        },
        headers=provider["headers"],
    )
    assert overlap.status_code == 422
