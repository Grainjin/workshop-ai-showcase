from datetime import datetime
from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from backend.core.clock import WORKSHOP_TIMEZONE, to_workshop_datetime
from backend import models
from backend.core.clock import utc_now
from backend.utils import customer_booking_actions
from backend.routers.customer import bookings as booking_router
from backend.schemas.booking import BookingCreate, BookingUpdate
from backend.utils.upload import validate_booking_attachments
from backend.utils.formatters import format_booking_response


def upload(filename: str, content_type: str, size: int = 1) -> UploadFile:
    return UploadFile(
        file=BytesIO(b"x" * size),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_booking_title_is_required_and_limited_to_30_words():
    with pytest.raises(ValueError):
        BookingCreate(
            provider_profile_id=1,
            service_category="plumbing",
            title=" ".join(["word"] * 31),
            service_description="Repair",
            service_address="Address",
            service_latitude=41,
            service_longitude=29,
            scheduled_start_time=datetime(2026, 10, 5, 10),
            scheduled_end_time=datetime(2026, 10, 5, 11),
        )
    with pytest.raises(ValueError):
        BookingUpdate(
            title="",
            service_description="Repair",
            service_address="Address",
            service_latitude=41,
            service_longitude=29,
            scheduled_start_time=datetime(2026, 10, 5, 10),
            scheduled_end_time=datetime(2026, 10, 5, 11),
        )


def test_booking_attachment_limits_are_checked_before_persistence():
    with pytest.raises(HTTPException) as too_many_images:
        validate_booking_attachments([upload(f"{index}.jpg", "image/jpeg") for index in range(6)])
    assert too_many_images.value.status_code == 422

    with pytest.raises(HTTPException) as too_many_videos:
        validate_booking_attachments([upload(f"{index}.mp4", "video/mp4") for index in range(3)])
    assert too_many_videos.value.status_code == 422

    with pytest.raises(HTTPException) as oversized_image:
        validate_booking_attachments([upload("large.jpg", "image/jpeg", 2 * 1024 * 1024 + 1)])
    assert oversized_image.value.status_code == 422

    with pytest.raises(HTTPException) as oversized_video:
        validate_booking_attachments([upload("large.mp4", "video/mp4", 10 * 1024 * 1024 + 1)])
    assert oversized_video.value.status_code == 422


def test_booking_create_and_update_time_contract_normalizes_naive_and_aware_inputs():
    naive = to_workshop_datetime(datetime(2026, 10, 5, 10))
    aware = to_workshop_datetime(datetime.fromisoformat("2026-10-05T07:00:00+00:00"))
    assert naive.isoformat() == "2026-10-05T10:00:00+03:00"
    assert aware.isoformat() == "2026-10-05T10:00:00+03:00"

    BookingCreate(
        provider_profile_id=1,
        service_category="plumbing",
        title="Mixed time",
        service_description="Repair",
        service_address="Address",
        service_latitude=41,
        service_longitude=29,
        scheduled_start_time=datetime(2026, 10, 5, 10),
        scheduled_end_time=datetime.fromisoformat("2026-10-05T08:00:00+00:00"),
    )


@pytest.mark.anyio
async def test_create_and_update_write_normalized_times_with_external_side_effects_stubbed(
    db_session, monkeypatch
):
    customer = models.User(name="Booking Customer", email="booking-time-customer@example.com", role="customer")
    provider_user = models.User(name="Booking Provider", email="booking-time-provider@example.com", role="provider")
    db_session.add_all([customer, provider_user])
    db_session.flush()
    provider = models.ProviderProfile(
        user_id=provider_user.id,
        business_name="Booking Time Provider",
        bio="Provider",
        service_province="Istanbul",
        tags="plumbing",
        certificate_name="Certificate",
        certificate_url="https://example.com/cert",
        hourly_rate=100,
        verification_status="approved",
        identity_verification_status="approved",
        qualification_verification_status="approved",
    )
    db_session.add(provider)
    db_session.flush()
    db_session.add(
        models.ProviderApprovedService(
            provider_profile_id=provider.id,
            service_category="plumbing",
            is_enabled=True,
        )
    )
    db_session.add(
        models.ProviderSubmerchant(
            provider_profile_id=provider.id,
            submerchant_type="PERSONAL",
            submerchant_external_id=f"test-booking-time-action-provider-{provider.id}",
            submerchant_key=f"test-booking-time-action-submerchant-{provider.id}",
            name="Booking Time Provider",
            email="booking-time-provider@example.com",
            gsm_number="+905551110099",
            address="Istanbul",
            iban="TR180006200119000006672315",
            contact_name="Booking Time",
            contact_surname="Provider",
            identity_number="10000000001",
            currency="TRY",
            status="active",
        )
    )
    db_session.flush()

    def fake_chat_room(customer_id, provider_profile_id, db):
        room = models.ChatRoom(
            customer_id=customer_id,
            provider_profile_id=provider_profile_id,
            created_at=utc_now(),
        )
        db.add(room)
        db.flush()
        return room

    def fake_chat_message(room, booking, sender_id, db, attachments):
        message = models.ChatMessage(
            chat_room_id=room.id,
            sender_id=sender_id,
            message="Booking created",
            message_type="text",
            created_at=utc_now(),
        )
        db.add(message)
        db.flush()
        return message

    async def no_push(*_args, **_kwargs):
        return None

    monkeypatch.setattr(customer_booking_actions, "ensure_provider_available_for_datetime_range", lambda *args: None)
    monkeypatch.setattr(customer_booking_actions, "get_or_create_chat_room", fake_chat_room)
    monkeypatch.setattr(customer_booking_actions, "create_booking_chat_message", fake_chat_message)
    monkeypatch.setattr(customer_booking_actions, "add_booking_status_history", lambda *args: None)
    monkeypatch.setattr(customer_booking_actions, "create_notification", lambda *args: None)
    monkeypatch.setattr(customer_booking_actions, "push_chat_message_to_room_members", no_push)
    monkeypatch.setattr(customer_booking_actions, "format_booking_detail_response", lambda booking, db: {"scheduled_start_time": booking.scheduled_start_time, "title": booking.title})
    monkeypatch.setattr(customer_booking_actions, "format_chat_room_response_with_unread", lambda *args: {})
    monkeypatch.setattr(customer_booking_actions, "format_chat_message_response", lambda *args: {})

    create_data = BookingCreate(
        provider_profile_id=provider.id,
        service_category="plumbing",
        title="Initial booking",
        service_description="Repair",
        service_address="Address",
        service_latitude=41,
        service_longitude=29,
        scheduled_start_time=datetime(2026, 10, 5, 10),
        scheduled_end_time=datetime.fromisoformat("2026-10-05T08:00:00+00:00"),
    )
    result = await customer_booking_actions.create_customer_booking_action(
        create_data, customer, db_session
    )
    booking = db_session.query(models.Booking).one()
    assert to_workshop_datetime(booking.scheduled_start_time) == datetime(
        2026, 10, 5, 10, tzinfo=WORKSHOP_TIMEZONE
    )
    reloaded_response = format_booking_response(booking)
    assert reloaded_response["scheduled_start_time"].isoformat() == "2026-10-05T10:00:00+03:00"
    assert result["booking"]["title"] == "Initial booking"

    monkeypatch.setattr(booking_router, "ensure_provider_available_for_datetime_range", lambda *args: None)
    monkeypatch.setattr(booking_router, "create_booking_status_chat_message", lambda *args: None)
    monkeypatch.setattr(booking_router, "add_booking_status_history", lambda *args: None)
    updated = await booking_router.update_pending_booking(
        booking.id,
        BookingUpdate(
            title="Updated booking",
            service_description="Repair",
            service_address="Address",
            service_latitude=41,
            service_longitude=29,
            scheduled_start_time=datetime.fromisoformat("2026-10-05T07:00:00+00:00"),
            scheduled_end_time=datetime.fromisoformat("2026-10-05T08:00:00+00:00"),
        ),
        customer,
        db_session,
    )
    db_session.refresh(booking)
    assert booking.title == "Updated booking"
    assert to_workshop_datetime(booking.scheduled_start_time) == datetime(
        2026, 10, 5, 10, tzinfo=WORKSHOP_TIMEZONE
    )
    assert format_booking_response(booking)["scheduled_start_time"].isoformat() == "2026-10-05T10:00:00+03:00"
    assert updated["data"]["booking"]["title"] == "Updated booking"
