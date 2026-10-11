import pytest

from backend import models
from backend.utils.upload import get_booking_upload_dir
from tests.conftest import PNG_BYTES, create_booking


def _put(client, path, headers, **kwargs):
    response = client.put(path, headers=headers, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()["data"]["booking"]


def _prepare(client, marketplace, stage):
    customer = marketplace["customer"]["headers"]
    provider = marketplace["provider"]["headers"]
    booking = create_booking(
        client, customer, marketplace["provider_profile"]["id"],
        attachments=[("attachments", ("photo.png", PNG_BYTES, "image/png"))],
    )
    if stage == "final-quote":
        _put(client, f"/provider/bookings/{booking['id']}/quote", provider,
             json={"quote_amount": 250, "visit_fee_amount": 40})
        _put(client, f"/customer/bookings/{booking['id']}/accept-quote", customer)
        checkout = client.put(f"/customer/bookings/{booking['id']}/pay", headers=customer,
                              json={"payment_stage": "visit_fee"})
        assert checkout.status_code == 200, checkout.text
        callback = client.post("/payments/iyzico/callback", data={"token": checkout.json()["data"]["token"]})
        assert callback.status_code == 200, callback.text
        _put(client, f"/provider/bookings/{booking['id']}/start-visit", provider,
             files={"proof_files": ("photo.png", PNG_BYTES, "image/png")})
    return booking, customer, provider


@pytest.mark.parametrize("stage", ["quote", "final-quote"])
def test_quote_files_survive_repeated_decline_and_requote(client, marketplace, stage):
    booking, customer, provider = _prepare(client, marketplace, stage)
    booking_id = booking["id"]
    quote_path = f"/provider/bookings/{booking_id}/{stage}"
    reject_path = f"/customer/bookings/{booking_id}/reject-{stage}"
    old_files = []
    for amount in (250, 275):
        detail = _put(
            client, quote_path, provider,
            data={"quote_amount": str(amount), "visit_fee_amount": "40", "quote_message": "Photo explains quote",
                  "quote_revision_id": "99999", "purpose": "completion_proof"},
            files=[("quote_files", ("photo.png", PNG_BYTES, "image/png")),
                   ("quote_files", ("report.pdf", b"%PDF-1.4 test report", "application/pdf"))],
        )
        current_id = detail["current_quote_revision_id"]
        assert current_id is not None
        quote_files = [item for item in detail["attachments"] if item["purpose"] == "quote_attachment"]
        current_files = [item for item in quote_files if item["quote_revision_id"] == current_id]
        assert len(current_files) == 2
        assert {item["original_file_name"] for item in current_files} == {"photo.png", "report.pdf"}
        assert len(quote_files) == len(old_files) + 2
        assert all(item in quote_files for item in old_files)
        assert booking["attachments"][0] in detail["attachments"]
        for headers in (customer, provider):
            response = client.get(f"/bookings/{booking_id}", headers=headers)
            assert response.status_code == 200, response.text
            assert response.json()["data"]["attachments"] == detail["attachments"]
            assert response.json()["data"]["current_quote_revision_id"] == current_id
        declined = _put(client, reject_path, customer, json={"status_note": "Please revise"})
        assert declined["current_quote_revision_id"] is None
        assert declined["attachments"] == detail["attachments"]
        old_files = quote_files

    detail = _put(client, quote_path, provider, json={"quote_amount": 300, "visit_fee_amount": 40})
    assert all(item["quote_revision_id"] != detail["current_quote_revision_id"] for item in old_files)
    assert all(item in detail["attachments"] for item in old_files)
    assert len({item["file_url"] for item in old_files}) == 4


@pytest.mark.parametrize("stage", ["quote", "final-quote"])
def test_invalid_quote_file_rolls_back_files_revision_and_booking(client, marketplace, db_session, stage):
    booking, customer, provider = _prepare(client, marketplace, stage)
    booking_id = booking["id"]
    before = client.get(f"/bookings/{booking_id}", headers=customer).json()["data"]
    directory = get_booking_upload_dir(booking_id)
    before_paths = set(directory.iterdir())
    before_revisions = db_session.query(models.BookingQuoteRevision).filter_by(booking_id=booking_id).count()
    response = client.put(
        f"/provider/bookings/{booking_id}/{stage}", headers=provider,
        data={"quote_amount": "250", "visit_fee_amount": "40"},
        files=[("quote_files", ("photo.png", PNG_BYTES, "image/png")),
               ("quote_files", ("invalid.exe", b"invalid", "application/octet-stream"))],
    )
    assert response.status_code == 400, response.text
    assert set(directory.iterdir()) == before_paths
    db_session.expire_all()
    assert db_session.query(models.BookingQuoteRevision).filter_by(booking_id=booking_id).count() == before_revisions
    after = client.get(f"/bookings/{booking_id}", headers=customer).json()["data"]
    assert after["status"] == before["status"]
    assert after["attachments"] == before["attachments"]
    assert after["current_quote_revision_id"] == before["current_quote_revision_id"]


@pytest.mark.parametrize("stage", ["quote", "final-quote"])
def test_quote_multipart_validation_and_permissions(client, marketplace, stage):
    booking, customer, provider = _prepare(client, marketplace, stage)
    path = f"/provider/bookings/{booking['id']}/{stage}"
    response = client.put(path, headers=provider, data={"quote_amount": "not-a-number"},
                          files={"quote_files": ("photo.png", PNG_BYTES, "image/png")})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["errors"][0]["field"] == "quote_amount"
    denied = client.put(path, headers=customer, data={"quote_amount": "250"},
                        files={"quote_files": ("photo.png", PNG_BYTES, "image/png")})
    assert denied.status_code == 403, denied.text
    detail = client.get(f"/bookings/{booking['id']}", headers=customer).json()["data"]
    assert all(item["purpose"] != "quote_attachment" for item in detail["attachments"])
