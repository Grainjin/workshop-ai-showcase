"""Demo proof is server selected; ordinary upload and booking invariants still apply."""

import pytest
from fastapi.testclient import TestClient

from backend import config, models
from backend.auth import get_db, require_provider
from backend.constants import DEMO_USER_EMAILS
from backend.main import app
from tests.conftest import PNG_BYTES, create_booking


@pytest.fixture
def demo_booking(client, marketplace, db_session, monkeypatch):
    booking = create_booking(client, marketplace["customer"]["headers"], marketplace["provider_profile"]["id"])
    provider = db_session.get(models.User, marketplace["provider"]["user"]["id"])
    provider.email = DEMO_USER_EMAILS["provider"]
    db_session.commit()
    monkeypatch.setattr(config, "DEMO_MODE", True)
    return booking


@pytest.mark.parametrize("action,start,end,purpose", [
    ("start-visit", "visit_paid", "provider_arrived", "arrival_evidence"),
    ("complete", "service_paid", "awaiting_confirmation", "completion_proof"),
])
def test_preset_action_uses_business_transition_and_retry_is_idempotent(
    client, marketplace, demo_booking, db_session, action, start, end, purpose,
):
    booking = db_session.get(models.Booking, demo_booking["id"])
    booking.status = start
    db_session.commit()
    path = f"/provider/demo/bookings/{booking.id}/{action}"
    headers = marketplace["provider"]["headers"]
    first = client.put(path, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["booking"]["status"] == end
    proof = db_session.query(models.BookingAttachment).filter_by(booking_id=booking.id).one()
    assert proof.purpose == purpose
    assert proof.uploaded_by_user_id == marketplace["provider"]["user"]["id"]
    assert proof.original_file_name.startswith("Simulated demo")
    assert proof.file_url.startswith("/demo/proof/")
    asset = client.get(proof.file_url)
    assert asset.status_code == 200
    assert "Simulated demo proof" in asset.text
    history_count = db_session.query(models.BookingStatusHistory).filter_by(booking_id=booking.id).count()
    retry = client.put(path, headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json()["data"]["booking"]["status"] == end
    assert db_session.query(models.BookingAttachment).filter_by(booking_id=booking.id).count() == 1
    assert db_session.query(models.BookingStatusHistory).filter_by(booking_id=booking.id).count() == history_count


@pytest.mark.parametrize("action,start", [("start-visit", "visit_paid"), ("complete", "service_paid")])
def test_existing_preset_does_not_bypass_invalid_current_state(
    client, marketplace, demo_booking, db_session, action, start,
):
    booking = db_session.get(models.Booking, demo_booking["id"])
    booking.status = start
    db_session.commit()
    path = f"/provider/demo/bookings/{booking.id}/{action}"
    headers = marketplace["provider"]["headers"]
    assert client.put(path, headers=headers).status_code == 200
    db_session.refresh(booking)
    booking.status = "cancelled"
    db_session.commit()
    assert client.put(path, headers=headers).status_code == 400
    assert db_session.query(models.BookingAttachment).filter_by(booking_id=booking.id).count() == 1


@pytest.mark.parametrize("action", ["start-visit", "complete"])
def test_preset_actions_enforce_owner_state_and_reject_client_evidence(client, marketplace, demo_booking, db_session, action):
    path = f"/provider/demo/bookings/{demo_booking['id']}/{action}"
    headers = marketplace["provider"]["headers"]
    assert client.put(path, headers=headers).status_code == 400  # pending is invalid
    assert client.put(path, headers=marketplace["customer"]["headers"]).status_code == 403
    assert client.put(path, headers=marketplace["admin"]["headers"]).status_code == 403
    for body in ({"json": {"file_url": "https://attacker.test/proof.png"}},
                 {"files": {"proof_files": ("arbitrary.png", PNG_BYTES, "image/png")}},
                 {"params": {"file_path": "/etc/passwd"}}):
        assert client.put(path, headers=headers, **body).status_code == 400
    booking = db_session.get(models.Booking, demo_booking["id"])
    # Same mapped provider, booking owned by another provider.
    other = models.ProviderProfile(user_id=marketplace["admin"]["user"]["id"],
        business_name="Other provider", bio="Test", service_province="Istanbul",
        hourly_rate=100, tags="plumbing", certificate_name="Test", certificate_url="/test.pdf")
    db_session.add(other)
    db_session.flush()
    booking.provider_profile_id = other.id
    db_session.commit()
    assert client.put(path, headers=headers).status_code == 404
    assert db_session.query(models.BookingAttachment).count() == 0


@pytest.mark.parametrize("action", ["start-visit", "complete"])
def test_ordinary_provider_cannot_use_demo_presets(client, marketplace, demo_booking, db_session, action):
    user = db_session.get(models.User, marketplace["provider"]["user"]["id"])
    user.email = "ordinary-provider@example.test"
    db_session.commit()
    response = client.put(f"/provider/demo/bookings/{demo_booking['id']}/{action}", headers=marketplace["provider"]["headers"])
    assert response.status_code == 404


@pytest.mark.parametrize("action", ["start-visit", "complete"])
def test_demo_presets_are_hidden_outside_demo_before_body_and_dependencies(monkeypatch, action):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    def forbidden():
        pytest.fail("Non-demo preset endpoint reached a dependency")
    for dep in (get_db, require_provider):
        app.dependency_overrides[dep] = forbidden
    try:
        response = TestClient(app).put(f"/provider/demo/bookings/1/{action}", content=b"{broken")
        assert response.status_code == 404
        assert response.json()["error"]["detail"] == "Not found"
    finally:
        for dep in (get_db, require_provider):
            app.dependency_overrides.pop(dep, None)
