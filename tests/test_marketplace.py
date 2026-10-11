from backend import models
from backend.database import SessionLocal
from backend.schemas import SubmerchantType
from backend.utils.marketplace_seed import build_demo_submerchant_data
from tests.conftest import PNG_BYTES, create_booking
import pytest
from decimal import Decimal
from tests.test_payment import demo_payment_mode, _demo_pending, _demo_pay


@pytest.mark.parametrize("amount,expected", [(40, "refunded"), (15, "partially_refunded")])
def test_demo_refund_uses_existing_states_and_one_success_limit(client, marketplace, demo_payment_mode, amount, expected):
    booking_id = _demo_pending(client, marketplace)
    paid = _demo_pay(client, marketplace, booking_id)
    assert paid.status_code == 200, paid.text
    payment_id = paid.json()["data"]["payment"]["id"]
    with SessionLocal() as db:
        booking = db.get(models.Booking, booking_id)
        booking.status = "provider_arrived"
        settlement = db.query(models.PaymentSettlement).filter_by(payment_id=payment_id).one()
        settlement.status = "approved"
        db.commit()
    for invalid in (0, -1, 41):
        response = client.post(f"/bookings/{booking_id}/refund-requests", json={"reason": "Demo refund", "refund_amount": invalid}, headers=marketplace["customer"]["headers"])
        assert response.status_code in {400, 422}, response.text
    requested = client.post(f"/bookings/{booking_id}/refund-requests", json={"reason": "Demo refund", "refund_amount": amount}, headers=marketplace["customer"]["headers"])
    assert requested.status_code == 200, requested.text
    refund_id = requested.json()["data"]["refund_request"]["id"]
    approved = client.put(f"/provider/refund-requests/{refund_id}/approve", headers=marketplace["provider"]["headers"])
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["booking"]["status"] == expected
    with SessionLocal() as db:
        payment = db.get(models.Payment, payment_id)
        assert payment.status == expected
        assert payment.external_status == "simulated"
        assert payment.payment_method == "demo"
        settlement = db.query(models.PaymentSettlement).filter_by(payment_id=payment_id).one()
        assert settlement.provider_recovery_amount == Decimal(str(amount)) * Decimal("0.90")
    repeated = client.post(f"/bookings/{booking_id}/refund-requests", json={"reason": "Again"}, headers=marketplace["customer"]["headers"])
    assert repeated.status_code == 400
    assert "successful refund" in repeated.text


def test_demo_settlement_approval_never_calls_external_client(client, marketplace, demo_payment_mode):
    from backend.tasks.marketplace_tasks import _approve_payment_settlement
    booking_id = _demo_pending(client, marketplace)
    paid = _demo_pay(client, marketplace, booking_id)
    assert paid.status_code == 200, paid.text
    payment_id = paid.json()["data"]["payment"]["id"]
    assert _approve_payment_settlement(payment_id)["status"] == "approved"
    assert _approve_payment_settlement(payment_id)["status"] == "approved"


def test_demo_mode_blocks_external_payout_changes_before_mutation(client, marketplace, demo_payment_mode):
    from tests.test_demo_restrictions import PAYOUT
    provider_id = marketplace["provider_profile"]["id"]
    with SessionLocal() as db:
        original = db.query(models.ProviderSubmerchant).filter_by(provider_profile_id=provider_id).one().name
    response = client.put("/provider/submerchant", json=PAYOUT, headers=marketplace["provider"]["headers"])
    assert response.status_code == 403, response.text
    with SessionLocal() as db:
        assert db.query(models.ProviderSubmerchant).filter_by(provider_profile_id=provider_id).one().name == original


def _remove_provider_submerchant(provider_profile_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(models.ProviderSubmerchant).filter(
            models.ProviderSubmerchant.provider_profile_id == provider_profile_id
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_demo_submerchant_fixtures_are_official_and_evenly_shuffled():
    values = []
    for index in range(1, 31):
        if index in {6, 7, 8, 9}:
            continue
        user = models.User(email=f"demo_provider_{index}@workshop.ai")
        provider = models.ProviderProfile()
        values.append(build_demo_submerchant_data(provider, user))

    counts = {}
    for value in values:
        key = value["submerchant_type"]
        counts[key] = counts.get(key, 0) + 1

    assert counts == {
        SubmerchantType.personal: 9,
        SubmerchantType.private_company: 9,
        SubmerchantType.limited_or_joint_stock_company: 8,
    }
    assert all(
        value["iban"] == "TR180006200119000006672315" for value in values
    )
    assert all(
        value.get("identity_number") in {None, "31300864726"} for value in values
    )


def test_provider_can_manage_submerchant_without_exposing_secret_key(
    client, marketplace
):
    provider = marketplace["provider"]["headers"]
    _remove_provider_submerchant(marketplace["provider_profile"]["id"])
    payload = {
        "submerchant_type": "PERSONAL",
        "name": "Can Provider",
        "email": "provider@example.com",
        "gsm_number": "+905551110000",
        "address": "Karakoy, Istanbul",
        "iban": "TR180006200119000006672315",
        "contact_name": "Can",
        "contact_surname": "Provider",
        "identity_number": "10000000001",
    }

    response = client.put("/provider/submerchant", json=payload, headers=provider)

    assert response.status_code == 200, response.text
    submerchant = response.json()["data"]["submerchant"]
    assert submerchant["status"] == "active"
    assert "submerchant_key" not in submerchant

    fetched = client.get("/provider/submerchant", headers=provider)
    assert fetched.status_code == 200, fetched.text
    assert "submerchant_key" not in fetched.json()["data"]["submerchant"]


def test_provider_recovers_existing_sandbox_submerchant_key(
    client, marketplace, fake_iyzico
):
    provider = marketplace["provider"]["headers"]
    provider_profile_id = marketplace["provider_profile"]["id"]
    _remove_provider_submerchant(provider_profile_id)

    async def create_existing_submerchant(_payload):
        return {
            "status": "failure",
            "errorCode": "2002",
            "errorMessage": "Sub merchant does exist for ID",
        }

    fake_iyzico.create_submerchant = create_existing_submerchant
    payload = {
        "submerchant_type": "PERSONAL",
        "name": "Can Provider",
        "email": "provider@example.com",
        "gsm_number": "+905551110000",
        "address": "Karakoy, Istanbul",
        "iban": "TR180006200119000006672315",
        "contact_name": "Can",
        "contact_surname": "Provider",
        "identity_number": "10000000001",
    }

    response = client.put("/provider/submerchant", json=payload, headers=provider)

    assert response.status_code == 200, response.text
    submerchant = response.json()["data"]["submerchant"]
    assert submerchant["status"] == "active"
    assert "submerchant_key" not in submerchant

    db = SessionLocal()
    try:
        stored = db.query(models.ProviderSubmerchant).filter_by(
            provider_profile_id=provider_profile_id
        ).one()
        assert stored.status == "active"
        assert stored.submerchant_key == f"test-submerchant-{stored.submerchant_external_id}"
    finally:
        db.close()


def test_provider_payout_details_require_valid_turkish_iban(client, marketplace):
    payload = {
        "submerchant_type": "PERSONAL",
        "name": "Can Provider",
        "email": "provider@example.com",
        "gsm_number": "+905551110000",
        "address": "Karakoy, Istanbul",
        "iban": "TR000000000000000000000000",
        "contact_name": "Can",
        "contact_surname": "Provider",
        "identity_number": "10000000001",
    }

    response = client.put(
        "/provider/submerchant",
        json=payload,
        headers=marketplace["provider"]["headers"],
    )

    assert response.status_code == 422, response.text
    assert "IBAN checksum is invalid" in response.text


def test_provider_company_details_allow_unused_personal_fields_to_be_null(
    client, marketplace
):
    payload = {
        "submerchant_type": "PRIVATE_COMPANY",
        "name": "Can Provider Ltd",
        "email": "provider@example.com",
        "gsm_number": "+905551110000",
        "address": "Karakoy, Istanbul",
        "iban": "TR180006200119000006672315",
        "contact_name": None,
        "contact_surname": None,
        "identity_number": None,
        "tax_office": "Istanbul Tax Office",
        "legal_company_title": "Can Provider Limited Company",
    }

    response = client.put(
        "/provider/submerchant",
        json=payload,
        headers=marketplace["provider"]["headers"],
    )

    assert response.status_code == 400, response.text
    assert "type cannot be changed" in response.text


def test_incomplete_provider_remains_recommendable_but_not_bookable(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_profile_id = marketplace["provider_profile"]["id"]
    _remove_provider_submerchant(provider_profile_id)

    recommendations = client.get(
        "/customer/home/recommendations",
        headers=customer,
    )
    assert recommendations.status_code == 200, recommendations.text
    assert any(
        item["id"] == provider_profile_id
        for item in recommendations.json()["data"]["items"]
    )

    response = client.post(
        "/bookings",
        data={
            "provider_profile_id": str(provider_profile_id),
            "service_category": "plumbing",
            "title": "Booking request",
            "service_description": "Kitchen pipe leak, needs on-site repair",
            "service_address": "Sultanahmet, Istanbul",
            "service_latitude": "41.0082",
            "service_longitude": "28.9784",
            "scheduled_start_time": "2026-10-05T08:00:00+00:00",
            "scheduled_end_time": "2026-10-05T10:00:00+00:00",
        },
        headers=customer,
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["detail"]["code"] == "PROVIDER_ONBOARDING_INCOMPLETE"


def test_payout_onboarding_can_start_before_provider_profile_approval(
    client, db_session, fake_iyzico
):
    del db_session, fake_iyzico
    from tests.conftest import register_session

    provider = register_session(
        client,
        "payout-before-qualification@example.com",
        role="provider",
        name="Payout First",
    )
    response = client.get("/provider/submerchant", headers=provider["headers"])

    assert response.status_code == 200, response.text
    assert response.json()["data"]["submerchant"] is None


def test_payment_flow_uses_marketplace_split_before_postauth(
    client, marketplace, fake_iyzico
):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_profile_id = marketplace["provider_profile"]["id"]
    booking = create_booking(client, customer, provider_profile_id)

    quoted = client.put(
        f"/provider/bookings/{booking['id']}/quote",
        json={"quote_amount": 180, "visit_fee_amount": 180, "quote_message": "Labour only"},
        headers=provider,
    )
    assert quoted.status_code == 200, quoted.text
    accepted = client.put(
        f"/customer/bookings/{booking['id']}/accept-quote", headers=customer
    )
    assert accepted.status_code == 200, accepted.text

    checkout = client.put(
        f"/customer/bookings/{booking['id']}/pay",
        json={"payment_method": "iyzico_checkout", "payment_stage": "visit_fee"},
        headers=customer,
    )
    assert checkout.status_code == 200, checkout.text
    token = checkout.json()["data"]["token"]
    payload = fake_iyzico.sessions[token]
    assert payload["basketItems"][0]["subMerchantKey"]
    assert payload["basketItems"][0]["subMerchantPrice"] == 162.0

    callback = client.post("/payments/iyzico/callback", data={"token": token})
    assert callback.status_code == 200, callback.text
    assert callback.json()["data"]["payment"]["settlement"] is None

    assert client.put(
        f"/provider/bookings/{booking['id']}/start-visit",
        files=[("proof_files", ("arrival.png", PNG_BYTES, "image/png"))],
        headers=provider,
    ).status_code == 200
    assert client.put(
        f"/provider/bookings/{booking['id']}/final-quote",
        json={"quote_amount": 180, "quote_message": "Labour only"},
        headers=provider,
    ).status_code == 200
    assert client.put(
        f"/customer/bookings/{booking['id']}/accept-final-quote", headers=customer
    ).status_code == 200
    service_checkout = client.put(
        f"/customer/bookings/{booking['id']}/pay",
        json={"payment_method": "iyzico_checkout", "payment_stage": "service_fee"},
        headers=customer,
    )
    assert service_checkout.status_code == 200, service_checkout.text
    service_callback = client.post(
        "/payments/iyzico/callback",
        data={"token": service_checkout.json()["data"]["token"]},
    )
    assert service_callback.status_code == 200, service_callback.text
    completed = client.put(
        f"/provider/bookings/{booking['id']}/complete",
        files=[("proof_files", ("proof.png", PNG_BYTES, "image/png"))],
        headers=provider,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["booking"]["status"] == "awaiting_confirmation"

    customer_payments = client.get("/customer/payments", headers=customer)
    assert customer_payments.status_code == 200, customer_payments.text
    customer_payment = customer_payments.json()["data"]["items"][0]
    assert customer_payment["settlement"] is None

    provider_payments = client.get("/provider/payments", headers=provider)
    assert provider_payments.status_code == 200, provider_payments.text
    assert provider_payments.json()["data"]["items"][0]["settlement"] is not None


def test_admin_can_filter_marketplace_payments_and_retry_failed_settlement(
    client, marketplace, monkeypatch
):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    admin = marketplace["admin"]["headers"]
    booking = create_booking(client, customer, marketplace["provider_profile"]["id"])

    assert client.put(
        f"/provider/bookings/{booking['id']}/quote",
        json={"quote_amount": 180, "visit_fee_amount": 20, "quote_message": "Labour only"},
        headers=provider,
    ).status_code == 200
    assert client.put(
        f"/customer/bookings/{booking['id']}/accept-quote", headers=customer
    ).status_code == 200
    checkout = client.put(
        f"/customer/bookings/{booking['id']}/pay",
        json={"payment_method": "iyzico_checkout", "payment_stage": "visit_fee"},
        headers=customer,
    )
    assert checkout.status_code == 200, checkout.text
    assert client.post(
        "/payments/iyzico/callback",
        data={"token": checkout.json()["data"]["token"]},
    ).status_code == 200
    assert client.put(
        f"/provider/bookings/{booking['id']}/start-visit",
        files=[("proof_files", ("arrival.png", PNG_BYTES, "image/png"))],
        headers=provider,
    ).status_code == 200
    assert client.put(
        f"/provider/bookings/{booking['id']}/final-quote",
        json={"quote_amount": 180, "quote_message": "Labour only"},
        headers=provider,
    ).status_code == 200
    assert client.put(
        f"/customer/bookings/{booking['id']}/accept-final-quote", headers=customer
    ).status_code == 200
    service_checkout = client.put(
        f"/customer/bookings/{booking['id']}/pay",
        json={"payment_method": "iyzico_checkout", "payment_stage": "service_fee"},
        headers=customer,
    )
    assert service_checkout.status_code == 200, service_checkout.text
    assert client.post(
        "/payments/iyzico/callback",
        data={"token": service_checkout.json()["data"]["token"]},
    ).status_code == 200
    assert client.put(
        f"/provider/bookings/{booking['id']}/complete",
        files=[("proof_files", ("proof.png", PNG_BYTES, "image/png"))],
        headers=provider,
    ).status_code == 200
    confirmed = client.put(
        f"/customer/bookings/{booking['id']}/confirm-complete", headers=customer
    )
    assert confirmed.status_code == 200, confirmed.text
    payment_id = confirmed.json()["data"]["payment"]["id"]

    db = SessionLocal()
    try:
        payment = db.get(models.Payment, payment_id)
        settlement = (
            db.query(models.PaymentSettlement)
            .filter(models.PaymentSettlement.payment_id == payment_id)
            .one()
        )
        settlement.status = "approval_failed"
        settlement.failure_code = "test_approval_failed"
        settlement.failure_message = "Approval needs a retry"
        settlement.iyzico_commission_fee = 43.15
        settlement.provider_payout_amount = 162
        settlement.merchant_payout_amount = 16.85
        db.commit()
        provider_profile_id = payment.provider_profile_id
    finally:
        db.close()

    filtered = client.get(
        "/admin/payments",
        params={
            "settlement_status": "approval_failed",
            "provider_profile_id": provider_profile_id,
            "booking_id": booking["id"],
        },
        headers=admin,
    )
    assert filtered.status_code == 200, filtered.text
    item = filtered.json()["data"]["items"][0]
    assert item["settlement"]["status"] == "approval_failed"
    assert item["settlement"]["iyzico_commission_fee"] == 43.15
    assert item["settlement"]["provider_payout_amount"] == 162
    assert item["settlement"]["merchant_payout_amount"] == 16.85

    monkeypatch.setattr(
        "backend.tasks.marketplace_tasks.enqueue_payment_settlement",
        lambda _payment_id: True,
    )
    retried = client.post(
        f"/admin/payments/{payment_id}/settlement/retry", headers=admin
    )
    assert retried.status_code == 200, retried.text
    assert retried.json()["data"]["payment"]["settlement"]["status"] == "approval_failed"

    unauthorized = client.get("/admin/payments", headers=customer)
    assert unauthorized.status_code == 403
