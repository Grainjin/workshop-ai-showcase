"""A local failure must not authorize charging an uncertain external attempt again."""

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
import pytest

from backend import models
from backend.database import SessionLocal
from backend.utils.customer_booking_actions import (
    apply_iyzico_checkout_result,
    pay_customer_booking_action,
)
from test_payment import _create_failed_checkout, _payment_snapshot


@pytest.mark.parametrize("stage", ["visit_fee", "service_fee"])
@pytest.mark.parametrize(
    "result",
    [
        {"paymentStatus": "SUCCESS", "paymentId": "charged", "paidPrice": "41", "currency": "TRY"},
        {"paymentStatus": "SUCCESS", "paymentId": "charged", "paidPrice": "40", "currency": "EUR"},
        {"paymentStatus": "SUCCESS", "paidPrice": "41", "currency": "TRY"},
        {"paymentStatus": "PENDING"},
        {"paymentStatus": "PROCESSING"},
        {"paymentStatus": "UNKNOWN"},
        {},
        {"paymentStatus": "FAILURE", "paymentId": "external-evidence"},
        {"paymentStatus": "SUCCESS", "fraudStatus": 0},
        {"paymentStatus": "FAILURE", "itemTransactions": [{"paymentTransactionId": "external-transaction"}]},
    ],
)
def test_uncertain_callback_requires_reconciliation_without_another_checkout(
    client, marketplace, fake_iyzico, monkeypatch, stage, result
):
    booking_id, original = _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch)
    with SessionLocal() as db:
        payment = db.get(models.Payment, original["id"])
        booking = db.get(models.Booking, booking_id)
        customer = db.get(models.User, payment.customer_id)
        payment.payment_stage = stage
        booking.status = "awaiting_visit_payment" if stage == "visit_fee" else "awaiting_service_payment"
        booking.final_quote_amount = 40
        db.commit()
        try:
            asyncio.run(apply_iyzico_checkout_result(payment, result, db))
        except HTTPException as exc:
            assert exc.status_code == 400
        snapshot = _payment_snapshot(payment)

        repeated = asyncio.run(pay_customer_booking_action(
            booking_id, "iyzico_checkout", customer, db,
            idempotency_key="failed-payment-original", payment_stage=stage,
        ))
        assert repeated["payment"]["id"] == payment.id
        assert _payment_snapshot(payment) == snapshot

        with pytest.raises(HTTPException) as blocked:
            asyncio.run(pay_customer_booking_action(
                booking_id, "iyzico_checkout", customer, db,
                idempotency_key="uncertain-retry", payment_stage=stage,
            ))
        assert blocked.value.status_code == 409
        assert "reconcil" in blocked.value.detail.lower()
        assert db.query(models.Payment).filter_by(booking_id=booking_id).count() == 1
        assert _payment_snapshot(payment) == snapshot
        assert len(fake_iyzico.sessions) == 0


@pytest.mark.parametrize("stage", ["visit_fee", "service_fee"])
@pytest.mark.parametrize("earlier_result", [{"paymentStatus": "SUCCESS"}, {}, {"paymentStatus": "PENDING"}])
def test_later_failure_cannot_erase_uncertain_callback_history(
    client, marketplace, fake_iyzico, monkeypatch, stage, earlier_result
):
    booking_id, original = _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch)
    with SessionLocal() as db:
        payment = db.get(models.Payment, original["id"])
        booking = db.get(models.Booking, booking_id)
        customer = db.get(models.User, payment.customer_id)
        payment.payment_stage = stage
        booking.status = "awaiting_visit_payment" if stage == "visit_fee" else "awaiting_service_payment"
        booking.final_quote_amount = 40
        db.commit()
        try:
            asyncio.run(apply_iyzico_checkout_result(payment, earlier_result, db))
        except HTTPException as exc:
            assert exc.status_code == 400
        asyncio.run(apply_iyzico_checkout_result(payment, {"paymentStatus": "FAILURE"}, db))
        with pytest.raises(HTTPException) as blocked:
            asyncio.run(pay_customer_booking_action(
                booking_id, "iyzico_checkout", customer, db,
                idempotency_key="after-later-failure", payment_stage=stage,
            ))
        assert blocked.value.status_code == 409
        assert db.query(models.Payment).filter_by(booking_id=booking_id).count() == 1
        assert len(fake_iyzico.sessions) == 0


@pytest.mark.parametrize("stage", ["visit_fee", "service_fee"])
@pytest.mark.parametrize("evidence", [
    {"external_payment_id": "external"}, {"iyzico_payment_id": "external"},
    {"payment_transaction_id": "external"}, {"external_status": "success"},
    {"iyzico_token": "external"}, {"checkout_url": "https://example.test/checkout"},
])
def test_pending_external_evidence_never_initializes_checkout(
    client, marketplace, fake_iyzico, monkeypatch, stage, evidence
):
    booking_id, original = _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch)
    with SessionLocal() as db:
        payment = db.get(models.Payment, original["id"])
        booking = db.get(models.Booking, booking_id)
        customer = db.get(models.User, payment.customer_id)
        payment.payment_stage = stage
        payment.status = "pending"
        payment.external_status = None
        for field, value in evidence.items():
            setattr(payment, field, value)
        booking.status = "awaiting_visit_payment" if stage == "visit_fee" else "awaiting_service_payment"
        booking.final_quote_amount = 40
        db.commit()
        snapshot = _payment_snapshot(payment)
        repeated = asyncio.run(pay_customer_booking_action(
            booking_id, "iyzico_checkout", customer, db,
            idempotency_key="failed-payment-original", payment_stage=stage,
        ))
        assert repeated["payment"]["id"] == payment.id
        assert _payment_snapshot(payment) == snapshot
        with pytest.raises(HTTPException) as blocked:
            asyncio.run(pay_customer_booking_action(
                booking_id, "iyzico_checkout", customer, db,
                idempotency_key="after-pending-evidence", payment_stage=stage,
            ))
        assert blocked.value.status_code == 409
        assert len(fake_iyzico.sessions) == 0


@pytest.mark.parametrize("stage", ["visit_fee", "service_fee"])
@pytest.mark.parametrize("state", ["checkout_created", "processing", "initialization_exception"])
def test_expiry_and_initialization_timeout_preserve_same_key_and_require_reconciliation(
    client, marketplace, fake_iyzico, monkeypatch, stage, state
):
    from backend.services.iyzico import IyzicoClientError

    booking_id, original = _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch)
    with SessionLocal() as db:
        payment = db.get(models.Payment, original["id"])
        booking = db.get(models.Booking, booking_id)
        customer = db.get(models.User, payment.customer_id)
        payment.payment_stage = stage
        booking.status = "awaiting_visit_payment" if stage == "visit_fee" else "awaiting_service_payment"
        booking.final_quote_amount = 40
        if state == "initialization_exception":
            async def timeout(payload):
                raise IyzicoClientError("Checkout initialization timed out")

            db.commit()
            with monkeypatch.context() as patch:
                patch.setattr(fake_iyzico, "initialize_checkout_form", timeout)
                with pytest.raises(HTTPException) as initialization:
                    asyncio.run(pay_customer_booking_action(
                        booking_id, "iyzico_checkout", customer, db,
                        idempotency_key="timeout-attempt", payment_stage=stage,
                    ))
                assert initialization.value.status_code == 502
            payment = db.query(models.Payment).filter_by(idempotency_key="timeout-attempt").one()
        else:
            payment.status = state
            payment.external_status = "checkout_initializing" if state == "processing" else "success"
            payment.processing_started_at = datetime.now(timezone.utc) - timedelta(days=1)
            payment.checkout_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            db.commit()
        snapshot = _payment_snapshot(payment)
        repeated = asyncio.run(pay_customer_booking_action(
            booking_id, "iyzico_checkout", customer, db,
            idempotency_key=payment.idempotency_key, payment_stage=stage,
        ))
        assert repeated["payment"]["id"] == payment.id
        assert _payment_snapshot(payment) == snapshot
        with pytest.raises(HTTPException) as blocked:
            asyncio.run(pay_customer_booking_action(
                booking_id, "iyzico_checkout", customer, db,
                idempotency_key="after-timeout", payment_stage=stage,
            ))
        assert blocked.value.status_code == 409
        assert len(fake_iyzico.sessions) == 0


@pytest.mark.parametrize("stage", ["visit_fee", "service_fee"])
def test_definitive_uncharged_callback_can_retry(client, marketplace, fake_iyzico, monkeypatch, stage):
    booking_id, original = _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch)
    with SessionLocal() as db:
        payment = db.get(models.Payment, original["id"])
        booking = db.get(models.Booking, booking_id)
        customer = db.get(models.User, payment.customer_id)
        payment.payment_stage = stage
        booking.status = "awaiting_visit_payment" if stage == "visit_fee" else "awaiting_service_payment"
        booking.final_quote_amount = 40
        db.commit()
        asyncio.run(apply_iyzico_checkout_result(payment, {"paymentStatus": "FAILURE"}, db))
        snapshot = _payment_snapshot(payment)
        retried = asyncio.run(pay_customer_booking_action(
            booking_id, "iyzico_checkout", customer, db,
            idempotency_key="definitive-retry", payment_stage=stage,
        ))
        assert retried["payment"]["id"] != payment.id
        assert retried["payment"]["status"] == "checkout_created"
        assert _payment_snapshot(payment) == snapshot
        assert db.query(models.Payment).filter_by(booking_id=booking_id).count() == 2
        assert len(fake_iyzico.sessions) == 1


@pytest.mark.parametrize("stage", ["visit_fee", "service_fee"])
@pytest.mark.parametrize("result", [
    {},
    {"status": "failure", "paymentId": "existing-payment"},
    {"status": "failure", "token": "existing-checkout"},
    {"status": "failure", "paymentPageUrl": "https://example.test/existing-checkout"},
    {"status": "failure", "paymentStatus": "SUCCESS"},
    {"status": "failure", "paymentTransactionId": "existing-transaction"},
])
def test_initialization_retains_uncertain_evidence_and_blocks_retry(
    client, marketplace, fake_iyzico, monkeypatch, stage, result
):
    booking_id, original = _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch)

    async def uncertain_initialize(payload):
        return result

    with SessionLocal() as db:
        payment = db.get(models.Payment, original["id"])
        booking = db.get(models.Booking, booking_id)
        customer = db.get(models.User, payment.customer_id)
        payment.payment_stage = stage
        booking.status = "awaiting_visit_payment" if stage == "visit_fee" else "awaiting_service_payment"
        booking.final_quote_amount = 40
        db.commit()
        with monkeypatch.context() as patch:
            patch.setattr(fake_iyzico, "initialize_checkout_form", uncertain_initialize)
            with pytest.raises(HTTPException) as initialization:
                asyncio.run(pay_customer_booking_action(
                    booking_id, "iyzico_checkout", customer, db,
                    idempotency_key="uncertain-initialize", payment_stage=stage,
                ))
            assert initialization.value.status_code == 502
        attempt = db.query(models.Payment).filter_by(idempotency_key="uncertain-initialize").one()
        snapshot = _payment_snapshot(attempt)
        with pytest.raises(HTTPException) as blocked:
            asyncio.run(pay_customer_booking_action(
                booking_id, "iyzico_checkout", customer, db,
                idempotency_key="after-uncertain-initialize", payment_stage=stage,
            ))
        assert blocked.value.status_code == 409
        assert "reconcil" in blocked.value.detail.lower()
        assert db.query(models.Payment).filter_by(booking_id=booking_id).count() == 2
        assert _payment_snapshot(attempt) == snapshot
        assert len(fake_iyzico.sessions) == 0


@pytest.mark.parametrize("stage", ["visit_fee", "service_fee"])
@pytest.mark.parametrize("earlier_state", ["failed", "checkout_created", "processing"])
def test_keyed_pending_attempt_cannot_bypass_earlier_uncertain_payment(
    client, marketplace, fake_iyzico, monkeypatch, stage, earlier_state
):
    booking_id, original = _create_failed_checkout(client, marketplace, fake_iyzico, monkeypatch)
    with SessionLocal() as db:
        payment = db.get(models.Payment, original["id"])
        booking = db.get(models.Booking, booking_id)
        customer = db.get(models.User, payment.customer_id)
        payment.payment_stage = stage
        payment.status = earlier_state
        payment.external_status = "success"
        payment.external_payment_id = "existing-external-payment"
        if earlier_state == "checkout_created":
            payment.checkout_expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        if earlier_state == "processing":
            payment.external_status = "checkout_initializing"
            payment.processing_started_at = datetime.now(timezone.utc)
        booking.status = "awaiting_visit_payment" if stage == "visit_fee" else "awaiting_service_payment"
        booking.final_quote_amount = 40
        queued = models.Payment(
            booking_id=booking_id, customer_id=customer.id,
            provider_profile_id=payment.provider_profile_id, amount=40, currency="TRY",
            payment_stage=stage, status="pending", idempotency_key="already-queued",
        )
        db.add(queued)
        db.commit()
        with pytest.raises(HTTPException) as blocked:
            asyncio.run(pay_customer_booking_action(
                booking_id, "iyzico_checkout", customer, db,
                idempotency_key="already-queued", payment_stage=stage,
            ))
        assert blocked.value.status_code == 409
        assert queued.status == "pending"
        assert db.query(models.Payment).filter_by(booking_id=booking_id).count() == 2
        assert len(fake_iyzico.sessions) == 0
