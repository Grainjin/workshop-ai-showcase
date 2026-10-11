"""Public demo identities cannot change credentials, upload files or moderate data."""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from backend import config, models
from backend.auth import get_current_user, get_db
from backend.main import app
from backend.routers import ai
from backend.utils import demo_mode, upload
from backend.utils.ai_pending_action import create_ai_pending_action
from tests.conftest import PNG_BYTES, create_booking


EMAILS = {
    "customer": "demo_customer_1@workshop.ai",
    "provider": "demo_provider_1@workshop.ai",
    "admin": "demo_admin@workshop.ai",
}
PROFILE = {
    "business_name": "Demo", "bio": "Test", "service_province": "Istanbul",
    "tags": ["plumbing"], "certificate_name": "Test", "certificate_url": "/test.pdf",
    "hourly_rate": 100,
}
QUALIFICATION = {
    "entity_type": "personal", "description": "Test", "contact_phone": "12345678",
    "business_address": "Test", "business_latitude": 41, "business_longitude": 29,
    "service_categories": ["plumbing"], "service_location_ids": [1],
    "qualification_files": [{"file_url": "/verification-files/qualification/test.pdf",
                              "original_file_name": "test.pdf", "content_type": "application/pdf"}],
}
PAYOUT = {
    "submerchant_type": "PERSONAL", "name": "Demo", "email": "demo@example.com",
    "gsm_number": "12345678", "address": "Test", "iban": "TR180006200119000006672315",
    "contact_name": "Demo", "contact_surname": "Test", "identity_number": "10000000001",
}
BOOKING = {
    "provider_profile_id": "999", "service_category": "plumbing", "title": "Demo",
    "service_description": "Kitchen pipe leak", "service_address": "Istanbul",
    "service_latitude": "41", "service_longitude": "29",
    "scheduled_start_time": "2026-10-15T10:00:00Z",
    "scheduled_end_time": "2026-10-15T12:00:00Z",
}


def attachment(field="file"):
    return {"files": {field: ("test.png", PNG_BYTES, "image/png")}}


SENSITIVE_ROUTES = [
    ("customer", "POST", "/auth/change-password", {"json": {"current_password": "old", "new_password": "New12345"}}),
    ("customer", "POST", "/auth/change-email", {"json": {"new_email": "next@example.com", "code": "123456"}}),
    ("customer", "POST", "/auth/email-code", {"json": {"purpose": "change_email", "new_email": "next@example.com"}}),
    ("customer", "POST", "/auth/email-code", {"json": {"purpose": "verify_email"}}),
    ("customer", "POST", "/auth/verify-email", {"json": {"code": "123456"}}),
    ("customer", "POST", "/auth/verify-phone", {"json": {"code": "123456"}}),
    ("customer", "POST", "/me/avatar", attachment()),
    ("customer", "POST", "/chats/999/attachments", attachment()),
    ("customer", "POST", "/bookings/999/attachments", attachment()),
    ("customer", "POST", "/bookings", {**attachment("attachments"), "data": BOOKING}),
    ("provider", "POST", "/provider/identity-verification", {**attachment("files"), "data": {"date_of_birth": "1990-01-01", "document_type": "passport"}}),
    ("provider", "POST", "/provider/qualification-files/upload", attachment("files")),
    ("provider", "POST", "/provider/qualification-verification", {"json": QUALIFICATION}),
    ("provider", "POST", "/provider/profile", {"json": PROFILE}),
    ("provider", "PUT", "/provider/profile", {"json": PROFILE}),
    ("provider", "POST", "/provider/certificates/upload", attachment()),
    ("provider", "POST", "/provider/portfolio", {**attachment("media_files"), "data": {"title": "Demo"}}),
    ("provider", "PUT", "/provider/bookings/999/quote", {**attachment("quote_files"), "data": {"quote_amount": "250", "visit_fee_amount": "40"}}),
    ("provider", "PUT", "/provider/bookings/999/final-quote", {**attachment("quote_files"), "data": {"quote_amount": "250", "visit_fee_amount": "40"}}),
    ("provider", "PUT", "/provider/bookings/999/start-visit", attachment("proof_files")),
    ("provider", "PUT", "/provider/bookings/999/complete", attachment("proof_files")),
    ("provider", "POST", "/provider/submerchant", {"json": PAYOUT}),
    ("provider", "PUT", "/provider/submerchant", {"json": PAYOUT}),
    ("admin", "PUT", "/admin/users/999/status", {"json": {"is_banned": True}}),
    ("admin", "PUT", "/admin/providers/999/verification", {"json": {"verification_status": "rejected", "verification_note": "Test"}}),
    ("admin", "PUT", "/admin/provider-portfolios/999/verification", {"json": {"verification_status": "rejected", "verification_note": "Test"}}),
    ("admin", "PUT", "/admin/identity-verifications/999/decision", {"json": {"status": "rejected", "review_note": "Test"}}),
    ("admin", "PUT", "/admin/qualification-verifications/999/decision", {"json": {"status": "rejected", "review_note": "Test"}}),
    ("admin", "PUT", "/admin/bookings/999/status", {"json": {"status": "cancelled", "status_note": "Test"}}),
    ("admin", "POST", "/admin/payments/999/settlement/retry", {}),
    ("admin", "PUT", "/admin/refund-requests/999/approve", {"json": {"admin_note": "Test"}}),
    ("admin", "PUT", "/admin/refund-requests/999/reject", {"json": {"admin_note": "Test"}}),
    ("admin", "PUT", "/admin/complaints/999/status", {"json": {"status": "rejected", "admin_note": "Test"}}),
    ("admin", "PUT", "/admin/reviews/999/visibility", {"json": {"is_visible": False}}),
    ("admin", "PUT", "/ai/oauth", {"json": {"auth": "key"}}),
    ("admin", "PUT", "/ai/oauth/key", {"json": {"api_key": "test"}}),
    ("admin", "DELETE", "/ai/oauth/key", {}),
    ("admin", "POST", "/ai/oauth/models", {"json": {"source": "key", "api_key": "test"}}),
] + [("admin", "POST", f"/ai/oauth/{provider}/{action}", {})
     for provider in ("chatgpt", "grok") for action in ("start", "cancel", "logout")]


@pytest.fixture
def demo_identity(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(upload, "UPLOAD_DIR", tmp_path / "public")
    monkeypatch.setattr(upload, "VERIFICATION_UPLOAD_DIR", tmp_path / "private")
    app.dependency_overrides[get_db] = lambda: db_session
    # OAuth functions touch local secrets or an external provider; never exercise them in RED.
    def unavailable(*args, **kwargs):
        raise HTTPException(503, "External authentication is unavailable in this test")
    for name in ("set_saved_auth", "save_admin_llm", "clear_admin_llm", "logout_chatgpt",
                 "logout_grok", "list_key_models", "list_subscription_models"):
        monkeypatch.setattr(ai, name, unavailable)
    for flow in (ai.chatgpt_oauth, ai.grok_oauth):
        monkeypatch.setattr(flow, "start", unavailable)
        monkeypatch.setattr(flow, "cancel", unavailable)

    def select(role, email=None):
        user = models.User(name="Demo Test", first_name="Demo", last_name="Test",
                           email=email or EMAILS[role], role=role, is_active=True,
                           is_banned=False, email_verified_at=datetime.now(timezone.utc))
        db_session.add(user)
        db_session.commit()
        if role == "provider":
            db_session.add(models.ProviderProfile(user_id=user.id, business_name="Test",
                bio="Test", service_province="Istanbul", hourly_rate=100, tags="plumbing",
                certificate_name="Test", certificate_url="/test.pdf",
                verification_status="approved", qualification_verification_status="approved",
                identity_verification_status="approved"))
            db_session.commit()
        app.dependency_overrides[get_current_user] = lambda: user
        return user
    yield select
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def assert_restricted(response):
    assert response.status_code == 403, response.text
    detail = response.json()["error"]["detail"]
    assert detail["code"] == "DEMO_RESTRICTED_ACTION"
    assert "demo" in detail["message"].lower()
    assert "@" not in detail["message"]


@pytest.mark.parametrize("role,method,path,body", SENSITIVE_ROUTES,
                         ids=[f"{method} {path}" for _, method, path, _ in SENSITIVE_ROUTES])
def test_sensitive_routes_reject_demo_before_mutation(client, demo_identity, tmp_path, role, method, path, body):
    demo_identity(role)
    assert_restricted(client.request(method, path, **body))
    assert not list(tmp_path.rglob("*.png"))


@pytest.mark.parametrize("path", ["/register", "/register/email-code", "/social-login", "/login", "/token"])
@pytest.mark.parametrize("body", [{}, {"content": b"{broken", "headers": {"Content-Type": "application/json"}}])
def test_demo_blocks_public_account_entry_before_body_or_credentials(client, monkeypatch, path, body):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    assert_restricted(client.post(path, **body))


@pytest.mark.parametrize("role", ["customer", "provider", "admin"])
@pytest.mark.parametrize("enabled,is_seeded", [(False, True), (False, False), (True, False)])
def test_guard_noop_outside_seeded_demo_accounts(monkeypatch, role, enabled, is_seeded):
    monkeypatch.setattr(config, "DEMO_MODE", enabled)
    user = models.User(role=role, email=EMAILS[role] if is_seeded else "ordinary@example.com")
    guard = getattr(demo_mode, "reject_demo_restricted_action", None)
    assert callable(guard), "Central demo restriction guard is missing"
    assert guard(user, "change_password") is None


@pytest.mark.parametrize("role", ["customer", "provider", "admin"])
def test_guard_uses_email_even_if_role_changes(monkeypatch, role):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    guard = getattr(demo_mode, "reject_demo_restricted_action", None)
    assert callable(guard), "Central demo restriction guard is missing"
    with pytest.raises(HTTPException) as error:
        guard(models.User(email=EMAILS[role], role="other"), "change_password")
    assert error.value.status_code == 403
    assert error.value.detail["code"] == "DEMO_RESTRICTED_ACTION"


@pytest.mark.parametrize("enabled,email", [(False, EMAILS["customer"]), (True, "ordinary@example.com")])
def test_avatar_still_works_outside_seeded_demo(client, demo_identity, monkeypatch, enabled, email):
    demo_identity("customer", email)
    monkeypatch.setattr(config, "DEMO_MODE", enabled)
    response = client.post("/me/avatar", **attachment())
    assert response.status_code == 200, response.text
    assert response.json()["data"]["file_url"].endswith(".png")


@pytest.mark.parametrize("stage", ["quote", "final-quote"])
def test_text_quotes_retain_normal_missing_booking_result(client, demo_identity, stage):
    demo_identity("provider")
    response = client.put(f"/provider/bookings/999/{stage}", json={"quote_amount": 250, "visit_fee_amount": 40})
    assert response.status_code == 404, response.text


def test_attachment_free_booking_retains_normal_missing_provider_result(client, demo_identity):
    demo_identity("customer")
    response = client.post("/bookings", data=BOOKING)
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("role,method,path,body", SENSITIVE_ROUTES)
def test_sensitive_routes_keep_non_demo_behavior(client, demo_identity, role, method, path, body):
    demo_identity(role, "ordinary@example.com")
    response = client.request(method, path, **body)
    assert response.status_code != 422, response.text
    assert "success" in response.json(), response.text
    detail = response.json().get("error", {}).get("detail")
    if isinstance(detail, dict):
        assert detail.get("code") != "DEMO_RESTRICTED_ACTION", response.text


@pytest.fixture
def mapped_demo_marketplace(marketplace, db_session, monkeypatch):
    # Build ordinary authenticated fixtures, then map their real persisted users.
    for role in EMAILS:
        db_session.get(models.User, marketplace[role]["user"]["id"]).email = EMAILS[role]
    db_session.commit()
    monkeypatch.setattr(config, "DEMO_MODE", True)
    return marketplace


@pytest.mark.parametrize("quote_format", ["json", "multipart"])
def test_demo_preserves_favorites_text_chat_bookings_quotes_and_payments(
    client, mapped_demo_marketplace, db_session, quote_format, monkeypatch,
):
    monkeypatch.setattr(config, "PAYMENT_MODE", "demo")
    monkeypatch.setattr("backend.services.iyzico.get_iyzico_client",
                        lambda: pytest.fail("Public demo must not instantiate iyzico"))
    customer = mapped_demo_marketplace["customer"]["headers"]
    provider = mapped_demo_marketplace["provider"]["headers"]
    provider_id = mapped_demo_marketplace["provider_profile"]["id"]
    favorite = client.post(f"/customer/favorites/{provider_id}", headers=customer)
    assert favorite.status_code == 200, favorite.text
    removed = client.delete(f"/customer/favorites/{provider_id}", headers=customer)
    assert removed.status_code == 200, removed.text

    booking = create_booking(client, customer, provider_id)
    room_id = booking["chat_room_id"]
    for headers, message in [(customer, "Can you repair the leak?"), (provider, "Yes.")]:
        sent = client.post(f"/chats/{room_id}/messages", json={"message": message}, headers=headers)
        assert sent.status_code == 200, sent.text
        assert sent.json()["data"]["chat_message"]["message"] == message

    quote = {"quote_amount": 250, "visit_fee_amount": 40, "quote_message": "Labour"}
    body = {"json": quote} if quote_format == "json" else {
        "data": quote, "files": {"unrelated": (None, "multipart without uploads")},
    }
    quoted = client.put(f"/provider/bookings/{booking['id']}/quote", headers=provider, **body)
    assert quoted.status_code == 200, quoted.text
    accepted = client.put(f"/customer/bookings/{booking['id']}/accept-quote", headers=customer)
    assert accepted.status_code == 200, accepted.text
    paid = client.put(f"/customer/bookings/{booking['id']}/pay", json={}, headers=customer)
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["payment"]["status"] == "paid"
    assert paid.json()["data"]["payment"]["payment_method"] == "demo"
    assert paid.json()["data"]["payment_page_url"] is None
    callback = client.post("/payments/iyzico/callback", data={"token": "external-token"})
    assert callback.status_code == 403, callback.text

    # Arrival evidence is intentionally restricted; fixture the seeded later stage.
    db_session.get(models.Booking, booking["id"]).status = "provider_arrived"
    db_session.commit()
    final = client.put(f"/provider/bookings/{booking['id']}/final-quote", headers=provider, **body)
    assert final.status_code == 200, final.text
    accepted_final = client.put(f"/customer/bookings/{booking['id']}/accept-final-quote", headers=customer)
    assert accepted_final.status_code == 200, accepted_final.text
    assert accepted_final.json()["data"]["payment"]["payment_method"] == "demo"
    service_paid = client.put(f"/customer/bookings/{booking['id']}/pay",
                              json={"payment_stage": "service_fee"}, headers=customer)
    assert service_paid.status_code == 200, service_paid.text
    assert service_paid.json()["data"]["booking"]["status"] == "service_paid"
    # Completion evidence remains restricted too; use the seeded confirmation state.
    db_session.get(models.Booking, booking["id"]).status = "awaiting_confirmation"
    db_session.commit()
    completed = client.put(f"/customer/bookings/{booking['id']}/confirm-complete", headers=customer)
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["booking"]["status"] == "completed"
    assert db_session.query(models.PaymentSettlement).filter_by(booking_id=booking["id"]).count() == 2


def test_demo_preserves_reviews_of_completed_seeded_bookings(
    client, mapped_demo_marketplace, db_session, monkeypatch,
):
    customer = mapped_demo_marketplace["customer"]["headers"]
    booking = create_booking(client, customer, mapped_demo_marketplace["provider_profile"]["id"])
    db_session.get(models.Booking, booking["id"]).status = "completed"
    db_session.commit()
    # Review embedding is a separate asynchronous effect, outside this test.
    monkeypatch.setattr("backend.routers.customer.feedback.enqueue_review_embedding_sync", lambda *a: None)
    reviewed = client.post(f"/bookings/{booking['id']}/review", headers=customer,
                           json={"rating": 5, "comment": "Helpful service."})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["review"]["rating"] == 5


def test_demo_preserves_ai_booking_confirmation(client, mapped_demo_marketplace, db_session):
    customer = mapped_demo_marketplace["customer"]
    booking = create_booking(client, customer["headers"], mapped_demo_marketplace["provider_profile"]["id"])
    action = create_ai_pending_action(customer["user"]["id"], "cancel_booking",
                                     {"booking_id": booking["id"]}, "Cancel booking", [], db_session)
    confirmed = client.post("/ai/actions/confirm", json={"action_id": action["id"]},
                            headers=customer["headers"])
    assert confirmed.status_code == 200, confirmed.text
    detail = client.get(f"/bookings/{booking['id']}", headers=customer["headers"])
    assert detail.json()["data"]["status"] == "cancelled"
