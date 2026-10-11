import pytest

from backend import models
from tests.conftest import PNG_BYTES, create_booking


def test_booking_attachments_stay_separate_through_pay_visit_completion_and_history(client, marketplace):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    same_name_file = ("photo.png", PNG_BYTES, "image/png")
    booking = create_booking(
        client, customer, marketplace["provider_profile"]["id"],
        attachments=[("attachments", same_name_file)],
    )
    booking_id = booking["id"]
    original_attachment = booking["attachments"][0]
    assert original_attachment["purpose"] == "customer_attachment"
    expected_purposes = ["customer_attachment"]

    def check_detail(detail):
        attachments = detail["attachments"]
        assert sorted(item["purpose"] for item in attachments) == sorted(expected_purposes)
        assert original_attachment in attachments
        assert len({item["file_url"] for item in attachments}) == len(attachments)
        return attachments

    def update(path, headers, **kwargs):
        response = client.put(path, headers=headers, **kwargs)
        assert response.status_code == 200, response.text
        check_detail(response.json()["data"]["booking"])
        return response.json()["data"]

    def pay(stage):
        checkout = update(
            f"/customer/bookings/{booking_id}/pay", customer, json={"payment_stage": stage},
        )
        callback = client.post("/payments/iyzico/callback", data={"token": checkout["token"]})
        assert callback.status_code == 200, callback.text
        check_detail(callback.json()["data"]["booking"])

    expected_purposes.append("quote_attachment")
    update(
        f"/provider/bookings/{booking_id}/quote", provider,
        data={"quote_amount": "250", "visit_fee_amount": "40"},
        files=[("quote_files", same_name_file)],
    )
    update(f"/customer/bookings/{booking_id}/accept-quote", customer)
    pay("visit_fee")
    expected_purposes.append("arrival_evidence")
    update(f"/provider/bookings/{booking_id}/start-visit", provider, files=[("proof_files", same_name_file)])
    expected_purposes.append("quote_attachment")
    update(
        f"/provider/bookings/{booking_id}/final-quote",
        provider,
        data={"quote_amount": "275"},
        files=[("quote_files", same_name_file)],
    )
    update(f"/customer/bookings/{booking_id}/accept-final-quote", customer)
    pay("service_fee")
    expected_purposes.append("completion_proof")
    update(f"/provider/bookings/{booking_id}/complete", provider, files=[("proof_files", same_name_file)])
    confirmed = update(f"/customer/bookings/{booking_id}/confirm-complete", customer)
    assert confirmed["booking"]["status"] == "completed"
    attachments = confirmed["booking"]["attachments"]
    assert {item["original_file_name"] for item in attachments} == {"photo.png"}

    for headers, list_path in ((customer, "/customer/bookings"), (provider, "/provider/bookings")):
        detail = client.get(f"/bookings/{booking_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["attachments"] == attachments
        history = client.get(list_path, params={"status": "completed"}, headers=headers)
        assert history.status_code == 200, history.text
        history_booking = next(item for item in history.json()["data"]["items"] if item["id"] == booking_id)
        assert history_booking["attachments"] == attachments
        chat_bookings = client.get(f"/chats/{booking['chat_room_id']}/bookings", headers=headers)
        assert chat_bookings.status_code == 200, chat_bookings.text
        chat_booking = next(item for item in chat_bookings.json()["data"]["items"] if item["id"] == booking_id)
        assert chat_booking["attachments"] == attachments

    refund = client.post(
        f"/bookings/{booking_id}/refund-requests", headers=customer,
        json={"reason": "Service issue", "refund_amount": 50},
    )
    assert refund.status_code == 200, refund.text
    check_detail(refund.json()["data"]["booking"])
    refund_id = refund.json()["data"]["refund_request"]["id"]
    refunded = update(f"/provider/refund-requests/{refund_id}/approve", provider)
    assert refunded["booking"]["status"] == "partially_refunded"
    for headers in (customer, provider):
        detail = client.get(f"/bookings/{booking_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["attachments"] == attachments


@pytest.mark.parametrize("status", ["pending", "quoted", "cancelled", "refunding", "refunded", "completed"])
def test_customer_extra_attachment_keeps_purpose_and_survives_status_changes(
    client, marketplace, db_session, status,
):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    booking = create_booking(client, customer, marketplace["provider_profile"]["id"])
    booking_id = booking["id"]
    uploaded = client.post(
        f"/bookings/{booking_id}/attachments", headers=customer,
        data={"purpose": "completion_proof"},  # A customer cannot spoof provider proof.
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    attachment = uploaded.json()["data"]
    assert attachment["purpose"] == "customer_attachment"

    booking_record = db_session.get(models.Booking, booking_id)
    booking_record.status = status
    db_session.commit()
    for headers in (customer, provider):
        detail = client.get(f"/bookings/{booking_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["attachments"] == [attachment]
        listing = client.get(f"/bookings/{booking_id}/attachments", headers=headers)
        assert listing.status_code == 200, listing.text
        assert listing.json()["data"]["items"] == [attachment]

    denied = client.post(
        f"/bookings/{booking_id}/attachments", headers=provider,
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
    )
    assert denied.status_code == 403, denied.text
