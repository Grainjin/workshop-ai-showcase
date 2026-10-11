from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend import models
from backend.database import SessionLocal
from tests.conftest import create_booking


@pytest.fixture
def demo_payment_mode(marketplace, monkeypatch):
    from backend import config
    monkeypatch.setattr(config, "PAYMENT_MODE", "demo")
    def forbidden_client():
        pytest.fail("Demo payments must never instantiate the iyzico client")
    monkeypatch.setattr("backend.services.iyzico.get_iyzico_client", forbidden_client)


def _demo_pending(client, marketplace, stage="visit_fee"):
    customer = marketplace["customer"]["headers"]
    booking = create_booking(client, customer, marketplace["provider_profile"]["id"])
    booking_id = booking["id"]
    quoted = client.put(f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 250, "visit_fee_amount": 40}, headers=marketplace["provider"]["headers"])
    assert quoted.status_code == 200, quoted.text
    accepted = client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer)
    assert accepted.status_code == 200, accepted.text
    if stage == "service_fee":
        with SessionLocal() as db:
            booking = db.get(models.Booking, booking_id)
            booking.status = "awaiting_service_payment"
            booking.final_quote_amount = Decimal("250")
            payment = db.query(models.Payment).filter_by(booking_id=booking_id).one()
            payment.payment_stage = stage
            payment.amount = Decimal("250")
            db.commit()
    return booking_id


def _demo_pay(client, marketplace, booking_id, key="demo-key", stage="visit_fee", **extra):
    return client.put(f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "demo", "payment_stage": stage, **extra},
        headers={**marketplace["customer"]["headers"], "Idempotency-Key": key})


@pytest.mark.parametrize("stage,expected,amount", [("visit_fee", "visit_paid", 40), ("service_fee", "service_paid", 250)])
def test_demo_payment_transitions_and_replay(client, marketplace, demo_payment_mode, stage, expected, amount):
    booking_id = _demo_pending(client, marketplace, stage)
    paid = _demo_pay(client, marketplace, booking_id, stage=stage)
    assert paid.status_code == 200, paid.text
    data = paid.json()["data"]
    payment = data["payment"]
    assert (payment["status"], payment["payment_method"], payment["external_status"]) == ("paid", "demo", "simulated")
    assert payment["amount"] == amount
    assert data.get("payment_page_url") is None
    assert payment["checkout_url"] is None
    assert payment["iyzico_token"] is None
    assert data["booking"]["status"] == expected
    assert data["booking"]["payment_method"] == "demo"
    with SessionLocal() as db:
        settlement = db.query(models.PaymentSettlement).filter_by(payment_id=payment["id"]).one()
        assert settlement.provider_share_amount == Decimal(str(amount)) * Decimal("0.90")
        assert settlement.status == "pending"
        history = db.query(models.BookingStatusHistory).filter_by(booking_id=booking_id, new_status=expected).one()
        assert history.old_status == ("awaiting_visit_payment" if stage == "visit_fee" else "awaiting_service_payment")
        assert db.query(models.Notification).filter_by(notification_type="payment_paid", related_id=payment["id"]).count() == 1
        assert db.query(models.ChatMessage).filter_by(related_id=booking_id, message_type="booking_status").count() >= 2
        history_count = db.query(models.BookingStatusHistory).filter_by(booking_id=booking_id).count()
        chat_count = db.query(models.ChatMessage).count()
        notification_count = db.query(models.Notification).count()
    replay = _demo_pay(client, marketplace, booking_id, stage=stage)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["payment"] == payment
    assert _demo_pay(client, marketplace, booking_id, key="new-key", stage=stage).status_code == 409
    with SessionLocal() as db:
        assert db.query(models.Payment).filter_by(booking_id=booking_id).count() == 1
        assert db.query(models.PaymentSettlement).filter_by(payment_id=payment["id"]).count() == 1
        assert db.query(models.BookingStatusHistory).filter_by(booking_id=booking_id).count() == history_count
        assert db.query(models.ChatMessage).count() == chat_count
        assert db.query(models.Notification).count() == notification_count


def test_demo_failed_attempt_replays_and_new_key_retries(client, marketplace, demo_payment_mode):
    booking_id = _demo_pending(client, marketplace)
    with SessionLocal() as db:
        payment = db.query(models.Payment).filter_by(booking_id=booking_id).one()
        payment.payment_method = "demo"
        payment.external_status = "simulated"
        payment.status = "failed"
        payment.failure_code = "demo_declined"
        payment.idempotency_key = "demo-key"
        db.commit()
        old_id = payment.id
        original = _payment_snapshot(payment)
    replay = _demo_pay(client, marketplace, booking_id)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["payment"]["status"] == "failed"
    retry = _demo_pay(client, marketplace, booking_id, key="retry-key")
    assert retry.status_code == 200, retry.text
    assert retry.json()["data"]["payment"]["id"] != old_id
    assert retry.json()["data"]["payment"]["status"] == "paid"
    with SessionLocal() as db:
        assert _payment_snapshot(db.get(models.Payment, old_id)) == original


@pytest.mark.parametrize("status,method,external", [("failed", "demo", "uncertain"), ("processing", "demo", "simulated"), ("failed", "iyzico_checkout", "failure")])
def test_demo_retry_rejects_non_simulated_definitive_failures(client, marketplace, demo_payment_mode, status, method, external):
    booking_id = _demo_pending(client, marketplace)
    with SessionLocal() as db:
        payment = db.query(models.Payment).filter_by(booking_id=booking_id).one()
        payment.status, payment.payment_method, payment.external_status = status, method, external
        payment.idempotency_key = "old-key"
        db.commit()
    assert _demo_pay(client, marketplace, booking_id, key="new-key").status_code == 409


def test_demo_payment_rejects_card_fields_and_cross_stage_key(client, marketplace, demo_payment_mode):
    booking_id = _demo_pending(client, marketplace)
    assert _demo_pay(client, marketplace, booking_id, cardNumber="4111111111111111").status_code == 422
    assert _demo_pay(client, marketplace, booking_id).status_code == 200
    assert _demo_pay(client, marketplace, booking_id, stage="service_fee").status_code == 409


def test_demo_mode_blocks_real_callback_even_for_existing_token(client, marketplace, demo_payment_mode):
    booking_id = _demo_pending(client, marketplace)
    with SessionLocal() as db:
        payment = db.query(models.Payment).filter_by(booking_id=booking_id).one()
        payment.iyzico_token = "old-real-token"
        db.commit()
    response = client.post("/payments/iyzico/callback", data={"token": "old-real-token"})
    assert response.status_code == 403


def test_public_demo_cannot_use_sandbox_checkout(client, marketplace, monkeypatch):
    from backend import config
    booking_id = _demo_pending(client, marketplace)
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "PAYMENT_MODE", "iyzico_sandbox")
    assert _demo_pay(client, marketplace, booking_id).status_code == 403


@pytest.mark.parametrize("public,mode", [(True, "iyzico_sandbox"), (False, "demo")])
def test_demo_configuration_blocks_iyzico_client_factory(monkeypatch, public, mode):
    from backend import config
    from backend.services import iyzico
    monkeypatch.setattr(config, "DEMO_MODE", public)
    monkeypatch.setattr(config, "PAYMENT_MODE", mode)
    with pytest.raises(iyzico.IyzicoClientError, match="disabled"):
        iyzico.get_iyzico_client()


def _create_checkout(client, customer_headers, provider_profile_id):
    booking = create_booking(client, customer_headers, provider_profile_id)
    booking_id = booking["id"]
    return booking_id


def _payment_snapshot(payment):
    return {
        column.name: getattr(payment, column.name) for column in models.Payment.__table__.columns
    }


def _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch):
    customer = marketplace["customer"]["headers"]
    booking_id = _create_checkout(client, customer, marketplace["provider_profile"]["id"])
    quoted = client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 250.50, "visit_fee_amount": 40},
        headers=marketplace["provider"]["headers"],
    )
    assert quoted.status_code == 200, quoted.text
    accepted = client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer)
    assert accepted.status_code == 200, accepted.text

    async def reject_checkout(payload):
        return {
            "status": "failure",
            "conversationId": payload["conversationId"],
            "errorCode": "card_declined",
            "errorMessage": "The card was declined",
        }

    with monkeypatch.context() as patch:
        patch.setattr(fake_iyzico, "initialize_checkout_form", reject_checkout)
        failed = client.put(
            f"/customer/bookings/{booking_id}/pay",
            json={"payment_method": "iyzico_checkout"},
            headers={**customer, "Idempotency-Key": "failed-payment-original"},
        )
    assert failed.status_code == 502, failed.text
    with SessionLocal() as db:
        payment = db.query(models.Payment).filter(models.Payment.booking_id == booking_id).one()
        assert payment.status == "failed"
        assert payment.failure_code == "card_declined"
        return booking_id, _payment_snapshot(payment)


def test_failed_payment_can_retry_with_new_idempotency_key(
    client, marketplace, fake_iyzico, monkeypatch
):
    booking_id, failed_snapshot = _create_failed_checkout(
        client, marketplace, fake_iyzico, monkeypatch
    )
    customer = marketplace["customer"]["headers"]
    assert len(fake_iyzico.sessions) == 0

    retried = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={**customer, "Idempotency-Key": "failed-payment-retry"},
    )

    assert retried.status_code == 200, retried.text
    replacement = retried.json()["data"]["payment"]
    assert replacement["id"] != failed_snapshot["id"]
    assert replacement["status"] == "checkout_created"
    assert replacement["idempotency_key"] == "failed-payment-retry"
    assert replacement["failure_code"] is None
    assert len(fake_iyzico.sessions) == 1
    payload = fake_iyzico.sessions[retried.json()["data"]["token"]]
    assert payload["conversationId"] == f"booking-{booking_id}-payment-{replacement['id']}"
    assert payload["paidPrice"] == 40.0

    continued = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={**customer, "Idempotency-Key": "failed-payment-another-new-key"},
    )
    assert continued.status_code == 200, continued.text
    assert continued.json()["data"]["payment"]["id"] == replacement["id"]
    assert len(fake_iyzico.sessions) == 1

    original = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={**customer, "Idempotency-Key": "failed-payment-original"},
    )
    assert original.status_code == 200, original.text
    assert original.json()["data"]["payment"]["id"] == failed_snapshot["id"]
    assert original.json()["data"]["payment"]["status"] == "failed"
    assert len(fake_iyzico.sessions) == 1

    with SessionLocal() as db:
        attempts = db.query(models.Payment).filter(models.Payment.booking_id == booking_id).all()
        assert len(attempts) == 2
        assert _payment_snapshot(db.get(models.Payment, failed_snapshot["id"])) == failed_snapshot
        new_payment = db.get(models.Payment, replacement["id"])
        for field in (
            "booking_id",
            "customer_id",
            "provider_profile_id",
            "amount",
            "currency",
            "payment_stage",
        ):
            assert getattr(new_payment, field) == failed_snapshot[field]
        assert new_payment.failed_at is None


def test_failed_payment_same_idempotency_key_returns_failed_attempt(
    client, marketplace, fake_iyzico, monkeypatch
):
    booking_id, failed_snapshot = _create_failed_checkout(
        client, marketplace, fake_iyzico, monkeypatch
    )

    repeated = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={
            **marketplace["customer"]["headers"],
            "Idempotency-Key": "failed-payment-original",
        },
    )

    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["data"]["payment"]["id"] == failed_snapshot["id"]
    assert repeated.json()["data"]["payment"]["status"] == "failed"
    assert len(fake_iyzico.sessions) == 0
    with SessionLocal() as db:
        assert db.query(models.Payment).filter(models.Payment.booking_id == booking_id).count() == 1
        assert _payment_snapshot(db.get(models.Payment, failed_snapshot["id"])) == failed_snapshot


@pytest.mark.parametrize("payment_stage", ["visit_fee", "service_fee"])
def test_replacement_payment_attempt_starts_pending(
    client, marketplace, fake_iyzico, monkeypatch, payment_stage
):
    from backend.utils.customer_booking_actions import create_replacement_payment_attempt

    _, failed_snapshot = _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        failed_payment = db.get(models.Payment, failed_snapshot["id"])
        failed_payment.payment_stage = payment_stage
        failed_payment.currency = "EUR"
        db.commit()
        original = _payment_snapshot(failed_payment)

        replacement = create_replacement_payment_attempt(
            failed_payment, Decimal("40.00"), "replacement-pending", now, db
        )

        assert replacement.id is not None
        assert replacement.id != failed_payment.id
        assert replacement.status == "pending"
        assert replacement.idempotency_key == "replacement-pending"
        assert replacement.created_at == now
        assert replacement.amount == Decimal("40.00")
        for field in (
            "booking_id",
            "customer_id",
            "provider_profile_id",
            "currency",
            "payment_stage",
        ):
            assert getattr(replacement, field) == original[field]
        for field in (
            "failed_at",
            "failure_code",
            "failure_message",
            "iyzico_token",
            "checkout_url",
            "conversation_id",
            "external_status",
        ):
            assert getattr(replacement, field) is None
        db.flush()
        db.refresh(failed_payment)
        assert _payment_snapshot(failed_payment) == original


def test_payment_checkout_is_idempotent_for_repeated_requests(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]
    booking_id = _create_checkout(client, customer, provider_id)

    quoted = client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 250.50, "visit_fee_amount": 40, "quote_message": "Includes parts"},
        headers=provider,
    )
    assert quoted.status_code == 200, quoted.text
    accepted = client.put(
        f"/customer/bookings/{booking_id}/accept-quote",
        headers=customer,
    )
    assert accepted.status_code == 200, accepted.text

    idempotency_key = "payment-test-repeat-1"
    first = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={**customer, "Idempotency-Key": idempotency_key},
    )
    second = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={**customer, "Idempotency-Key": idempotency_key},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["data"]["payment"]["id"] == first.json()["data"]["payment"]["id"]
    assert second.json()["data"]["token"] == first.json()["data"]["token"]

    payments = client.get("/customer/payments", headers=customer)
    assert payments.status_code == 200, payments.text
    attempts = [
        payment
        for payment in payments.json()["data"]["items"]
        if payment["booking_id"] == booking_id
    ]
    assert len(attempts) == 1
    assert attempts[0]["status"] == "checkout_created"
    assert attempts[0]["idempotency_key"] == idempotency_key


def test_expired_checkout_requires_reconciliation_before_new_key(client, marketplace, fake_iyzico):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]
    booking_id = _create_checkout(client, customer, provider_id)

    client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 250.50, "visit_fee_amount": 40, "quote_message": "Includes parts"},
        headers=provider,
    )
    client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer)

    first = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={**customer, "Idempotency-Key": "payment-test-expiry-1"},
    )
    assert first.status_code == 200, first.text
    payment_id = first.json()["data"]["payment"]["id"]

    db = SessionLocal()
    try:
        payment = db.get(models.Payment, payment_id)
        payment.checkout_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    second = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={**customer, "Idempotency-Key": "payment-test-expiry-2"},
    )
    assert second.status_code == 409, second.text
    assert "reconcil" in second.text.lower()

    payments = client.get("/customer/payments", headers=customer)
    attempts = [
        payment
        for payment in payments.json()["data"]["items"]
        if payment["booking_id"] == booking_id
    ]
    assert len(attempts) == 1
    assert attempts[0]["id"] == payment_id
    assert attempts[0]["status"] == "checkout_created"
    assert len(fake_iyzico.sessions) == 1


def test_payment_callback_is_idempotent(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]
    booking_id = _create_checkout(client, customer, provider_id)

    client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 180, "visit_fee_amount": 30, "quote_message": "Labour only"},
        headers=provider,
    )
    client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer)
    checkout = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers=customer,
    )
    token = checkout.json()["data"]["token"]

    first = client.post("/payments/iyzico/callback", data={"token": token})
    second = client.post("/payments/iyzico/callback", data={"token": token})

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["payment"]["status"] == "paid"
    assert second.json()["data"]["payment"]["status"] == "paid"
    assert second.json()["data"]["booking"]["status"] == "visit_paid"


def test_payment_callback_returns_to_the_checkout_browser_origin(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]
    booking_id = _create_checkout(client, customer, provider_id)

    client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 180, "visit_fee_amount": 30},
        headers=provider,
    )
    client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer)

    frontend_origin = "http://127.0.0.1:8090"
    checkout = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={
            **customer,
            "Origin": "http://localhost:8090",
            "Idempotency-Key": "return-origin-test",
        },
    )
    assert checkout.status_code == 200, checkout.text

    continued_checkout = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers={
            **customer,
            "Origin": frontend_origin,
            "Idempotency-Key": "return-origin-test",
        },
    )
    assert continued_checkout.status_code == 200, continued_checkout.text
    assert continued_checkout.json()["data"]["token"] == checkout.json()["data"]["token"]

    callback = client.post(
        "/payments/iyzico/callback",
        data={"token": checkout.json()["data"]["token"]},
        follow_redirects=False,
    )

    assert callback.status_code == 303, callback.text
    assert callback.headers["location"].startswith(
        f"{frontend_origin}/payment-result?booking_id={booking_id}&payment_status=paid"
    )


def test_payment_callback_rejects_amount_mismatch(client, marketplace, fake_iyzico):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]
    booking_id = _create_checkout(client, customer, provider_id)

    client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 180, "visit_fee_amount": 30, "quote_message": "Labour only"},
        headers=provider,
    )
    client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer)
    checkout = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers=customer,
    )
    fake_iyzico.retrieve_amount_override = "181"

    callback = client.post(
        "/payments/iyzico/callback",
        data={"token": checkout.json()["data"]["token"]},
    )

    assert callback.status_code == 400
    assert "currency" not in callback.text.lower()
    assert "amount" in callback.text.lower()
