from datetime import timedelta

import pytest

from backend import config, models
from backend.services import email_service, email_verification_service
from backend.services.email_service import OUTBOX, EmailDeliveryError
from tests.conftest import (
    create_admin_session,
    last_emailed_code,
    register,
    register_session,
)


def _send(client, headers, purpose="verify_email", new_email=None):
    payload = {"purpose": purpose}
    if new_email is not None:
        payload["new_email"] = new_email
    return client.post("/auth/email-code", json=payload, headers=headers)


def _wrong_code(code: str) -> str:
    return "000000" if code != "000000" else "111111"


def _age_codes(db_session, delta: timedelta):
    for record in db_session.query(models.EmailVerificationCode).all():
        record.created_at = record.created_at - delta
        record.expires_at = record.expires_at - delta
    db_session.commit()


def test_verify_email_rejects_any_code_until_one_is_sent(client):
    customer = register_session(client, "no-code@example.com")

    rejected = client.post(
        "/auth/verify-email",
        json={"code": "123456"},
        headers=customer["headers"],
    )

    assert rejected.status_code == 400
    assert "request a new code" in rejected.json()["message"].lower()


def test_sent_code_is_mailed_and_only_its_hash_is_stored(client, db_session):
    customer = register_session(client, "mailed@example.com")

    sent = _send(client, customer["headers"])

    assert sent.status_code == 200, sent.text
    assert sent.json()["data"] == {
        "sent_to": "mailed@example.com",
        "expires_in_seconds": 600,
        "resend_after_seconds": 60,
    }
    code = last_emailed_code("mailed@example.com")
    record = (
        db_session.query(models.EmailVerificationCode)
        .filter_by(purpose="verify_email")
        .one()
    )
    assert code not in (record.code_hash, record.code_salt)


def test_wrong_code_counts_attempts_then_locks_the_code(client):
    customer = register_session(client, "guess@example.com")
    _send(client, customer["headers"])
    code = last_emailed_code("guess@example.com")
    wrong = _wrong_code(code)

    for remaining in (4, 3, 2, 1):
        response = client.post(
            "/auth/verify-email", json={"code": wrong}, headers=customer["headers"]
        )
        assert response.status_code == 400
        assert f"{remaining} attempts left" in response.json()["message"]

    locked = client.post(
        "/auth/verify-email", json={"code": wrong}, headers=customer["headers"]
    )
    assert locked.status_code == 400
    assert "too many wrong attempts" in locked.json()["message"].lower()

    # The right code no longer works once the code is locked.
    after_lock = client.post(
        "/auth/verify-email", json={"code": code}, headers=customer["headers"]
    )
    assert after_lock.status_code == 400


def test_code_cannot_be_used_twice(client):
    customer = register_session(client, "twice@example.com")
    _send(client, customer["headers"])
    code = last_emailed_code("twice@example.com")

    first = client.post("/auth/verify-email", json={"code": code}, headers=customer["headers"])
    second = client.post("/auth/verify-email", json={"code": code}, headers=customer["headers"])

    assert first.status_code == 200, first.text
    assert second.status_code == 400


def test_expired_code_is_rejected(client, db_session):
    customer = register_session(client, "expired@example.com")
    _send(client, customer["headers"])
    code = last_emailed_code("expired@example.com")
    _age_codes(db_session, timedelta(minutes=11))

    response = client.post("/auth/verify-email", json={"code": code}, headers=customer["headers"])

    assert response.status_code == 400
    assert "expired" in response.json()["message"].lower()


def test_resend_waits_for_cooldown_and_replaces_the_old_code(client, db_session):
    customer = register_session(client, "resend@example.com")
    _send(client, customer["headers"])
    first_code = last_emailed_code("resend@example.com")

    too_soon = _send(client, customer["headers"])
    assert too_soon.status_code == 429
    assert "wait" in too_soon.json()["message"].lower()

    _age_codes(db_session, timedelta(seconds=61))
    resent = _send(client, customer["headers"])
    assert resent.status_code == 200, resent.text
    second_code = last_emailed_code("resend@example.com")

    if first_code != second_code:
        old = client.post(
            "/auth/verify-email", json={"code": first_code}, headers=customer["headers"]
        )
        assert old.status_code == 400

    new = client.post(
        "/auth/verify-email", json={"code": second_code}, headers=customer["headers"]
    )
    assert new.status_code == 200, new.text


def test_hourly_send_limit(client, db_session):
    customer = register_session(client, "hourly@example.com")

    for _ in range(email_verification_service.MAX_SENDS_PER_HOUR):
        assert _send(client, customer["headers"]).status_code == 200
        _age_codes(db_session, timedelta(seconds=61))

    limited = _send(client, customer["headers"])
    assert limited.status_code == 429
    assert "too many codes" in limited.json()["message"].lower()


def test_failed_delivery_returns_502_and_does_not_start_cooldown(client, monkeypatch):
    customer = register_session(client, "smtp-down@example.com")

    def broken_send(to, subject, body):
        raise EmailDeliveryError("connection refused")

    monkeypatch.setattr(email_verification_service, "send_email", broken_send)
    failed = _send(client, customer["headers"])
    assert failed.status_code == 502

    monkeypatch.undo()
    retried = _send(client, customer["headers"])
    assert retried.status_code == 200, retried.text


def test_change_email_code_goes_to_the_new_address_only(client):
    customer = register_session(client, "current@example.com")
    OUTBOX.clear()  # drop the sign-up email

    sent = _send(client, customer["headers"], "change_email", "New@Example.com")

    assert sent.status_code == 200, sent.text
    assert [message.to for message in OUTBOX] == ["new@example.com"]


def test_change_email_code_is_bound_to_the_address_it_was_sent_to(client):
    customer = register_session(client, "bound@example.com")
    _send(client, customer["headers"], "change_email", "first@example.com")
    code = last_emailed_code("first@example.com")

    swapped = client.post(
        "/auth/change-email",
        json={"new_email": "other@example.com", "code": code},
        headers=customer["headers"],
    )

    assert swapped.status_code == 400
    me = client.get("/me", headers=customer["headers"])
    assert me.json()["data"]["email"] == "bound@example.com"


def test_verify_code_cannot_confirm_an_email_change(client):
    customer = register_session(client, "purpose@example.com")
    _send(client, customer["headers"])
    code = last_emailed_code("purpose@example.com")

    response = client.post(
        "/auth/change-email",
        json={"new_email": "purpose@example.com", "code": code},
        headers=customer["headers"],
    )

    assert response.status_code == 400


def test_change_email_rejects_current_address_and_requires_new_email(client):
    customer = register_session(client, "same@example.com")

    same = _send(client, customer["headers"], "change_email", "Same@Example.com")
    missing = _send(client, customer["headers"], "change_email")

    assert same.status_code == 400
    assert missing.status_code == 422


def test_change_email_rechecks_the_address_is_still_free(client):
    customer = register_session(client, "racer@example.com")
    _send(client, customer["headers"], "change_email", "contested@example.com")
    code = last_emailed_code("contested@example.com")
    assert register(client, email="contested@example.com").status_code == 200

    response = client.post(
        "/auth/change-email",
        json={"new_email": "contested@example.com", "code": code},
        headers=customer["headers"],
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["message"].lower()


def test_email_code_requires_sign_in(client):
    assert client.post("/auth/email-code", json={"purpose": "verify_email"}).status_code == 401


def test_smtp_backend_without_credentials_fails_cleanly(monkeypatch):
    monkeypatch.setattr(config, "EMAIL_BACKEND", "smtp")
    monkeypatch.setattr(config, "SMTP_USERNAME", "")
    monkeypatch.setattr(config, "SMTP_PASSWORD", "")

    with pytest.raises(EmailDeliveryError):
        email_service.send_email("someone@example.com", "Subject", "Body")


GATED_PATHS = ("/customer/favorites", "/notifications", "/ai/tasks")


def test_unverified_customer_is_blocked_until_email_is_verified(client):
    customer = register_session(client, "gate@example.com", verified=False)
    headers = customer["headers"]

    for path in GATED_PATHS:
        blocked = client.get(path, headers=headers)
        assert blocked.status_code == 403, path
        assert "verify your email" in blocked.json()["message"].lower()

    # Account endpoints stay open so the user can verify or sign out.
    assert client.get("/me", headers=headers).status_code == 200
    assert _send(client, headers).status_code == 200
    verified = client.post(
        "/auth/verify-email",
        json={"code": last_emailed_code("gate@example.com")},
        headers=headers,
    )
    assert verified.status_code == 200, verified.text

    for path in GATED_PATHS:
        assert client.get(path, headers=headers).status_code == 200, path


def test_unverified_provider_is_blocked(client):
    provider = register_session(
        client, "gate-provider@example.com", role="provider", verified=False
    )

    blocked = client.get("/provider/profile", headers=provider["headers"])

    assert blocked.status_code == 403
    assert "verify your email" in blocked.json()["message"].lower()


def test_wrong_role_still_reports_the_role_error(client):
    customer = register_session(client, "role-first@example.com", verified=False)

    response = client.get("/provider/profile", headers=customer["headers"])

    assert response.status_code == 403
    assert "only providers" in response.json()["message"].lower()


def test_admin_is_exempt_from_email_verification(client, db_session):
    admin = create_admin_session(client, db_session)
    user = db_session.get(models.User, admin["user"]["id"])
    user.email_verified_at = None
    db_session.commit()

    assert client.get("/notifications", headers=admin["headers"]).status_code == 200


def _signup_payload(email, code):
    return {
        "first_name": "Sign",
        "last_name": "Up",
        "email": email,
        "password": "Signup123",
        "confirm_password": "Signup123",
        "tos_accepted": True,
        "role": "customer",
        "email_code": code,
    }


def test_signup_needs_the_mailed_code_and_starts_verified(client):
    sent = client.post("/register/email-code", json={"email": "New.User@Example.com"})
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["sent_to"] == "new.user@example.com"
    code = last_emailed_code("new.user@example.com")

    created = client.post("/register", json=_signup_payload("new.user@example.com", code))

    assert created.status_code == 200, created.text
    assert created.json()["data"]["user"]["email_verified"] is True
    session = client.post(
        "/login",
        data={"username": "new.user@example.com", "password": "Signup123"},
    ).json()["data"]
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    assert client.get("/customer/favorites", headers=headers).status_code == 200


def test_signup_without_a_code_is_rejected(client):
    payload = _signup_payload("nocode@example.com", "123456")
    del payload["email_code"]
    assert client.post("/register", json=payload).status_code == 422

    never_sent = client.post("/register", json=_signup_payload("nocode@example.com", "123456"))
    assert never_sent.status_code == 400


def test_signup_with_a_wrong_code_creates_no_account(client, db_session):
    client.post("/register/email-code", json={"email": "wrong@example.com"})
    code = last_emailed_code("wrong@example.com")

    rejected = client.post(
        "/register", json=_signup_payload("wrong@example.com", _wrong_code(code))
    )

    assert rejected.status_code == 400
    assert "attempts left" in rejected.json()["message"]
    assert db_session.query(models.User).filter_by(email="wrong@example.com").count() == 0


def test_signup_code_only_works_for_the_address_it_was_sent_to(client):
    client.post("/register/email-code", json={"email": "owner@example.com"})
    code = last_emailed_code("owner@example.com")

    stolen = client.post("/register", json=_signup_payload("thief@example.com", code))

    assert stolen.status_code == 400


def test_signup_code_cannot_be_reused(client):
    client.post("/register/email-code", json={"email": "once@example.com"})
    code = last_emailed_code("once@example.com")
    assert client.post("/register", json=_signup_payload("once@example.com", code)).status_code == 200

    again = client.post("/register", json=_signup_payload("once@example.com", code))

    assert again.status_code == 400
    assert "already registered" in again.json()["message"].lower()


def test_signup_code_is_refused_for_a_registered_address(client):
    register(client, email="taken-signup@example.com")
    OUTBOX.clear()

    response = client.post("/register/email-code", json={"email": "Taken-Signup@example.com"})

    assert response.status_code == 400
    assert "already registered" in response.json()["message"].lower()
    assert OUTBOX == []


def test_signup_code_resend_waits_for_cooldown(client):
    first = client.post("/register/email-code", json={"email": "cool@example.com"})
    second = client.post("/register/email-code", json={"email": "cool@example.com"})

    assert first.status_code == 200
    assert second.status_code == 429


def test_signup_codes_are_limited_per_client_ip(client, monkeypatch):
    monkeypatch.setattr(email_verification_service, "MAX_REGISTER_SENDS_PER_IP_PER_HOUR", 2)

    statuses = [
        client.post("/register/email-code", json={"email": f"ip{n}@example.com"}).status_code
        for n in range(3)
    ]

    assert statuses == [200, 200, 429]
