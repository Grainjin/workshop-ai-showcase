from tests.conftest import PNG_BYTES, create_booking


def _booking_status_chat_messages(client, headers, room_id):
    response = client.get(f"/chats/{room_id}/messages", headers=headers)
    assert response.status_code == 200, response.text
    return [
        message
        for message in response.json()["data"]["items"]
        if message["message_type"] == "booking_status"
    ]


def test_customer_bookings_require_auth(client):
    response = client.get("/customer/bookings")
    assert response.status_code == 401


def test_legacy_payment_routes_are_removed(client):
    create_payment = client.post(
        "/bookings/1/payments",
        json={"payment_method": "iyzico_checkout"},
    )
    pay_payment = client.put("/payments/1/pay")

    assert create_payment.status_code == 404
    assert pay_payment.status_code == 404


def test_customer_profile_round_trip(client, marketplace):
    headers = marketplace["customer"]["headers"]
    created = client.post(
        "/customer/profile",
        json={
            "phone_number": "+905551112233",
            "address": "1 Demo Street",
            "service_province": "Istanbul",
            "latitude": 41.0082,
            "longitude": 28.9784,
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["profile"]["service_province"] == "Istanbul"

    fetched = client.get("/customer/profile", headers=headers)
    assert fetched.status_code == 200
    body = fetched.json()["data"]
    profile = body.get("profile", body)
    assert profile["phone_number"] == "+905551112233"


def test_booking_quote_pay_complete_review_flow(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]

    booking = create_booking(client, customer, provider_id)
    assert booking["status"] == "pending"
    booking_id = booking["id"]

    quoted = client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 250.5, "visit_fee_amount": 40, "quote_message": "Includes parts"},
        headers=provider,
    )
    assert quoted.status_code == 200, quoted.text
    assert quoted.json()["data"]["booking"]["status"] == "quoted"

    accepted = client.put(
        f"/customer/bookings/{booking_id}/accept-quote",
        headers=customer,
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["booking"]["status"] == "awaiting_visit_payment"

    paid = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers=customer,
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["booking"]["status"] == "awaiting_visit_payment"
    assert paid.json()["data"]["payment"]["status"] == "checkout_created"
    assert paid.json()["data"]["payment"]["currency"] == "TRY"
    callback = client.post(
        "/payments/iyzico/callback",
        data={"token": paid.json()["data"]["token"]},
    )
    assert callback.status_code == 200, callback.text
    assert callback.json()["data"]["booking"]["status"] == "visit_paid"
    assert callback.json()["data"]["payment"]["status"] == "paid"

    started = client.put(
        f"/provider/bookings/{booking_id}/start-visit",
        files=[("proof_files", ("arrival.png", PNG_BYTES, "image/png"))],
        headers=provider,
    )
    assert started.status_code == 200, started.text
    assert started.json()["data"]["booking"]["status"] == "provider_arrived"

    final_quote = client.put(
        f"/provider/bookings/{booking_id}/final-quote",
        json={"quote_amount": 275, "quote_message": "Additional parts"},
        headers=provider,
    )
    assert final_quote.status_code == 200, final_quote.text
    assert final_quote.json()["data"]["booking"]["status"] == "final_quote_sent"

    final_accept = client.put(
        f"/customer/bookings/{booking_id}/accept-final-quote",
        headers=customer,
    )
    assert final_accept.status_code == 200, final_accept.text
    assert final_accept.json()["data"]["booking"]["status"] == "awaiting_service_payment"

    service_payment = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout", "payment_stage": "service_fee"},
        headers=customer,
    )
    assert service_payment.status_code == 200, service_payment.text
    service_callback = client.post(
        "/payments/iyzico/callback",
        data={"token": service_payment.json()["data"]["token"]},
    )
    assert service_callback.status_code == 200, service_callback.text
    assert service_callback.json()["data"]["booking"]["status"] == "service_paid"

    completed = client.put(
        f"/provider/bookings/{booking_id}/complete",
        files=[("proof_files", ("proof.png", PNG_BYTES, "image/png"))],
        headers=provider,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["booking"]["status"] == "awaiting_confirmation"
    confirmed = client.put(
        f"/customer/bookings/{booking_id}/confirm-complete",
        headers=customer,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["booking"]["status"] == "completed"
    completed_messages = _booking_status_chat_messages(
        client, customer, booking["chat_room_id"]
    )
    assert completed_messages[-1]["metadata"]["new_status"] == "completed"
    assert (
        completed_messages[-1]["metadata"]["title"]
        == "Customer confirmed service completion"
    )

    reviewed = client.post(
        f"/bookings/{booking_id}/review",
        json={"rating": 5, "comment": "Arrived on time and fixed the leak."},
        headers=customer,
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["review"]["rating"] == 5

    public = client.get(f"/providers/{provider_id}/reviews")
    assert public.status_code == 200, public.text
    items = public.json()["data"]["items"]
    assert any(item["rating"] == 5 for item in items)


def test_final_quote_can_be_declined_and_revised_without_new_arrival_evidence(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    booking = create_booking(client, customer, marketplace["provider_profile"]["id"])
    booking_id = booking["id"]
    room_id = booking["chat_room_id"]
    assert client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 200, "visit_fee_amount": 40},
        headers=provider,
    ).status_code == 200
    assert client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer).status_code == 200
    visit_checkout = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_stage": "visit_fee"},
        headers=customer,
    )
    assert visit_checkout.status_code == 200, visit_checkout.text
    assert client.post(
        "/payments/iyzico/callback", data={"token": visit_checkout.json()["data"]["token"]}
    ).status_code == 200
    assert client.put(
        f"/provider/bookings/{booking_id}/start-visit",
        files=[("proof_files", ("arrival.png", PNG_BYTES, "image/png"))],
        headers=provider,
    ).status_code == 200
    messages = _booking_status_chat_messages(client, customer, room_id)
    assert any(
        message["metadata"]["title"] == "Provider started the visit"
        and message["metadata"]["detail"]
        == "Provider arrived and submitted visit evidence"
        for message in messages
    )
    first = client.put(
        f"/provider/bookings/{booking_id}/final-quote",
        json={"quote_amount": 220, "quote_message": "First final quote"},
        headers=provider,
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["booking"]["status_note"] == "First final quote"
    messages = _booking_status_chat_messages(client, customer, room_id)
    assert any(
        message["metadata"]["title"] == "Provider submitted the final quote"
        and message["metadata"]["detail"] == "First final quote"
        for message in messages
    )
    declined = client.put(
        f"/customer/bookings/{booking_id}/reject-final-quote",
        json={"status_note": "Please revise the parts cost"},
        headers=customer,
    )
    assert declined.status_code == 200, declined.text
    assert declined.json()["data"]["booking"]["status"] == "awaiting_final_quote"
    declined_final = declined.json()["data"]["booking"]["last_declined_final_quote"]
    assert declined_final["quote_amount"] == 220
    assert declined_final["visit_fee_amount"] == 40
    assert declined_final["decline_reason"] == "Please revise the parts cost"
    messages = _booking_status_chat_messages(client, provider, room_id)
    assert any(
        message["metadata"]["title"] == "Customer declined the final quote"
        and message["metadata"]["detail"] == "Please revise the parts cost"
        for message in messages
    )
    revised = client.put(
        f"/provider/bookings/{booking_id}/final-quote",
        json={"quote_amount": 210, "quote_message": "Revised final quote"},
        headers=provider,
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["data"]["booking"]["status"] == "final_quote_sent"
    revised_booking = revised.json()["data"]["booking"]
    assert revised_booking["final_quote_amount"] == 210
    assert revised_booking["status_note"] == "Revised final quote"
    assert revised_booking["last_declined_final_quote"]["quote_amount"] == 220
    accepted = client.put(
        f"/customer/bookings/{booking_id}/accept-final-quote",
        headers=customer,
    )
    assert accepted.status_code == 200, accepted.text
    messages = _booking_status_chat_messages(client, provider, room_id)
    assert any(
        message["metadata"]["title"] == "Customer accepted the final quote"
        and message["metadata"]["detail"]
        == "Customer accepted the final quote and is waiting to pay"
        for message in messages
    )


def test_initial_quote_can_be_rejected_and_resubmitted(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    booking_id = create_booking(client, customer, marketplace["provider_profile"]["id"])["id"]
    first = client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 100, "visit_fee_amount": 20},
        headers=provider,
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["booking"]["visit_fee_amount"] == 20
    assert first.json()["data"]["booking"]["total_amount"] == 120
    rejected = client.put(
        f"/customer/bookings/{booking_id}/reject-quote",
        json={"status_note": "Too expensive"},
        headers=customer,
    )
    assert rejected.status_code == 200, rejected.text
    previous = rejected.json()["data"]["booking"]["last_declined_quote"]
    assert previous["visit_fee_amount"] == 20
    assert previous["expected_service_amount"] == 100
    assert previous["decline_reason"] == "Too expensive"
    invalid = client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 10, "visit_fee_amount": 20},
        headers=provider,
    )
    assert invalid.status_code == 422, invalid.text
    second = client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 80, "visit_fee_amount": 20},
        headers=provider,
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["booking"]["status"] == "quoted"


def test_refund_and_complaint_on_paid_booking(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    admin = marketplace["admin"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]

    booking_id = create_booking(client, customer, provider_id)["id"]
    client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 180, "visit_fee_amount": 30, "quote_message": "Labour only"},
        headers=provider,
    )
    client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer)
    paid = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout"},
        headers=customer,
    )
    assert paid.status_code == 200, paid.text
    callback = client.post(
        "/payments/iyzico/callback",
        data={"token": paid.json()["data"]["token"]},
    )
    assert callback.status_code == 200, callback.text

    early_refund = client.post(
        f"/bookings/{booking_id}/refund-requests",
        json={"reason": "Refund requested before completion"},
        headers=customer,
    )
    assert early_refund.status_code == 400, early_refund.text

    started = client.put(
        f"/provider/bookings/{booking_id}/start-visit",
        files=[("proof_files", ("arrival.png", PNG_BYTES, "image/png"))],
        headers=provider,
    )
    assert started.status_code == 200, started.text
    visit_refund = client.post(
        f"/bookings/{booking_id}/refund-requests",
        json={"reason": "The provider arrived but the visit will not continue"},
        headers=customer,
    )
    assert visit_refund.status_code == 200, visit_refund.text
    cancelled_visit_refund = client.put(
        f"/refund-requests/{visit_refund.json()['data']['refund_request']['id']}/cancel",
        headers=customer,
    )
    assert cancelled_visit_refund.status_code == 200, cancelled_visit_refund.text
    assert cancelled_visit_refund.json()["data"]["booking"]["status"] == "provider_arrived"

    final_quote = client.put(
        f"/provider/bookings/{booking_id}/final-quote",
        json={"quote_amount": 180, "visit_fee_amount": 30, "quote_message": "Labour only"},
        headers=provider,
    )
    assert final_quote.status_code == 200, final_quote.text
    final_quote_acceptance = client.put(
        f"/customer/bookings/{booking_id}/accept-final-quote",
        headers=customer,
    )
    assert final_quote_acceptance.status_code == 200, final_quote_acceptance.text
    service_payment = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout", "payment_stage": "service_fee"},
        headers=customer,
    )
    assert service_payment.status_code == 200, service_payment.text
    service_callback = client.post(
        "/payments/iyzico/callback",
        data={"token": service_payment.json()["data"]["token"]},
    )
    assert service_callback.status_code == 200, service_callback.text

    completed = client.put(
        f"/provider/bookings/{booking_id}/complete",
        files=[("proof_files", ("proof.png", PNG_BYTES, "image/png"))],
        headers=provider,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["booking"]["status"] == "awaiting_confirmation"

    confirm_stage_refund = client.post(
        f"/bookings/{booking_id}/refund-requests",
        json={"reason": "The completed work needs a refund before confirmation"},
        headers=customer,
    )
    assert confirm_stage_refund.status_code == 200, confirm_stage_refund.text
    assert confirm_stage_refund.json()["data"]["refund_request"]["previous_booking_status"] == "awaiting_confirmation"
    restored_confirmation = client.put(
        f"/refund-requests/{confirm_stage_refund.json()['data']['refund_request']['id']}/cancel",
        headers=customer,
    )
    assert restored_confirmation.status_code == 200, restored_confirmation.text
    assert restored_confirmation.json()["data"]["booking"]["status"] == "awaiting_confirmation"

    cancel_at_confirmation = client.put(
        f"/customer/bookings/{booking_id}/close-final-quote",
        json={"status_note": "This action must not bypass the refund flow"},
        headers=customer,
    )
    assert cancel_at_confirmation.status_code == 400, cancel_at_confirmation.text

    confirmed = client.put(
        f"/customer/bookings/{booking_id}/confirm-complete",
        headers=customer,
    )
    assert confirmed.status_code == 200, confirmed.text

    complaint = client.post(
        f"/bookings/{booking_id}/complaints",
        json={"reason": "Technician was two hours late"},
        headers=customer,
    )
    assert complaint.status_code == 200, complaint.text
    complaint_id = complaint.json()["data"]["complaint"]["id"]

    resolved = client.put(
        f"/admin/complaints/{complaint_id}/status",
        json={"status": "resolved", "admin_note": "Spoke with both parties"},
        headers=admin,
    )
    assert resolved.status_code == 200, resolved.text

    refund = client.post(
        f"/bookings/{booking_id}/refund-requests",
        json={"reason": "Work was not finished"},
        headers=customer,
    )
    assert refund.status_code == 200, refund.text
    refund_id = refund.json()["data"]["refund_request"]["id"]
    assert refund.json()["data"]["booking"]["status"] == "refunding"

    provider_cancel_attempt = client.put(
        f"/refund-requests/{refund_id}/cancel",
        headers=provider,
    )
    assert provider_cancel_attempt.status_code == 403, provider_cancel_attempt.text

    cancelled = client.put(
        f"/refund-requests/{refund_id}/cancel",
        headers=customer,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["booking"]["status"] == "completed"

    retry = client.post(
        f"/bookings/{booking_id}/refund-requests",
        json={"reason": "Work was still not finished", "refund_amount": 90},
        headers=customer,
    )
    assert retry.status_code == 200, retry.text
    retry_id = retry.json()["data"]["refund_request"]["id"]
    assert retry_id != refund_id

    approved = client.put(
        f"/provider/refund-requests/{retry_id}/approve",
        headers=provider,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["booking"]["status"] == "partially_refunded"
    refund_details = approved.json()["data"]["booking"]["current_refund_request"]
    assert refund_details["status"] == "approved"
    assert refund_details["reason"] == "Work was still not finished"
    assert refund_details["refund_amount"] == 90.0

    second_successful_refund = client.post(
        f"/bookings/{booking_id}/refund-requests",
        json={"reason": "A second successful refund should not be possible"},
        headers=customer,
    )
    assert second_successful_refund.status_code == 400, second_successful_refund.text
    assert "successful refund" in second_successful_refund.text


def test_changed_final_quote_requires_new_service_payment_before_capture(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    provider_id = marketplace["provider_profile"]["id"]
    booking_id = create_booking(client, customer, provider_id)["id"]

    assert client.put(
        f"/provider/bookings/{booking_id}/quote",
        json={"quote_amount": 180, "visit_fee_amount": 30, "quote_message": "Initial quote"},
        headers=provider,
    ).status_code == 200
    assert client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer).status_code == 200
    visit_payment = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout", "payment_stage": "visit_fee"},
        headers=customer,
    )
    assert visit_payment.status_code == 200, visit_payment.text
    assert client.post(
        "/payments/iyzico/callback", data={"token": visit_payment.json()["data"]["token"]}
    ).status_code == 200
    assert client.put(
        f"/provider/bookings/{booking_id}/start-visit",
        files=[("proof_files", ("arrival.png", PNG_BYTES, "image/png"))],
        headers=provider,
    ).status_code == 200
    final_quote = client.put(
        f"/provider/bookings/{booking_id}/final-quote",
        json={"quote_amount": 220, "quote_message": "Additional parts"},
        headers=provider,
    )
    assert final_quote.status_code == 200, final_quote.text
    assert client.put(
        f"/customer/bookings/{booking_id}/accept-final-quote", headers=customer
    ).status_code == 200
    service_payment = client.put(
        f"/customer/bookings/{booking_id}/pay",
        json={"payment_method": "iyzico_checkout", "payment_stage": "service_fee"},
        headers=customer,
    )
    assert service_payment.status_code == 200, service_payment.text
    assert client.post(
        "/payments/iyzico/callback", data={"token": service_payment.json()["data"]["token"]}
    ).status_code == 200

    completed = client.put(
        f"/provider/bookings/{booking_id}/complete",
        files=[("proof_files", ("proof.png", PNG_BYTES, "image/png"))],
        headers=provider,
    )
    assert completed.status_code == 200, completed.text
    captured = client.put(
        f"/customer/bookings/{booking_id}/confirm-complete", headers=customer
    )
    assert captured.status_code == 200, captured.text
    assert captured.json()["data"]["booking"]["status"] == "completed"
    assert captured.json()["data"]["payment"]["status"] == "paid"
    payments = client.get("/customer/payments", headers=customer)
    assert payments.status_code == 200, payments.text
    assert len([item for item in payments.json()["data"]["items"] if item["booking_id"] == booking_id]) == 2


def test_unapproved_provider_cannot_be_booked(client):
    from tests.conftest import create_provider_profile, register_session

    customer = register_session(client, "c2@example.com", role="customer")
    provider = register_session(client, "p2@example.com", role="provider")
    profile = create_provider_profile(client, provider["headers"])
    response = client.post(
        "/bookings",
        data={
            "provider_profile_id": str(profile["id"]),
            "service_category": "plumbing",
            "title": "Tap repair",
            "service_description": "Tap repair",
            "service_address": "Kadikoy, Istanbul",
            "service_latitude": "40.990",
            "service_longitude": "29.030",
            "scheduled_start_time": "2026-10-05T10:00:00+00:00",
            "scheduled_end_time": "2026-10-05T12:00:00+00:00",
        },
        headers=customer["headers"],
    )
    assert response.status_code == 409
    assert response.json()["error"]["detail"]["code"] == "PROVIDER_ONBOARDING_INCOMPLETE"
