from backend import models
from backend.core.clock import utc_now
from backend.utils import customer_booking_actions
from backend.utils import formatters
from backend.routers.customer import bookings as booking_router
from tests.conftest import register_session


def _provider(db_session, client):
    customer = register_session(client, "booking-time-http-customer@example.com", role="customer")
    provider_user = models.User(
        name="Booking Time HTTP Provider", email="booking-time-http-provider@example.com", role="provider"
    )
    db_session.add(provider_user)
    db_session.flush()
    profile = models.ProviderProfile(
        user_id=provider_user.id,
        business_name="HTTP Provider",
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
    db_session.add(profile)
    db_session.flush()
    db_session.add(
        models.ProviderApprovedService(
            provider_profile_id=profile.id,
            service_category="plumbing",
            is_enabled=True,
        )
    )
    db_session.commit()
    db_session.refresh(profile)
    db_session.add(
        models.ProviderSubmerchant(
            provider_profile_id=profile.id,
            submerchant_type="PERSONAL",
            submerchant_external_id=f"test-booking-time-provider-{profile.id}",
            submerchant_key=f"test-booking-time-submerchant-{profile.id}",
            name="HTTP Provider",
            email="booking-time-http-provider@example.com",
            gsm_number="+905551110099",
            address="Istanbul",
            iban="TR180006200119000006672315",
            contact_name="HTTP",
            contact_surname="Provider",
            identity_number="10000000001",
            currency="TRY",
            status="active",
        )
    )
    db_session.commit()
    return customer, profile


def _stub_booking_side_effects(monkeypatch):
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

    monkeypatch.setattr(
        customer_booking_actions,
        "ensure_provider_available_for_datetime_range",
        lambda *args: None,
    )
    monkeypatch.setattr(customer_booking_actions, "get_or_create_chat_room", fake_chat_room)
    monkeypatch.setattr(
        customer_booking_actions, "create_booking_chat_message", fake_chat_message
    )
    monkeypatch.setattr(
        customer_booking_actions, "add_booking_status_history", lambda *args: None
    )
    monkeypatch.setattr(customer_booking_actions, "create_notification", lambda *args: None)
    monkeypatch.setattr(customer_booking_actions, "push_chat_message_to_room_members", no_push)
    monkeypatch.setattr(booking_router, "ensure_provider_available_for_datetime_range", lambda *args: None)
    monkeypatch.setattr(booking_router, "create_booking_status_chat_message", lambda *args: None)
    monkeypatch.setattr(booking_router, "add_booking_status_history", lambda *args: None)
    monkeypatch.setattr(formatters, "is_user_online", lambda *_args: False)


def _form(provider_id, title):
    return {
        "provider_profile_id": str(provider_id),
        "service_category": "plumbing",
        "title": title,
        "service_description": "Repair",
        "service_address": "Address",
        "service_latitude": "41",
        "service_longitude": "29",
        "scheduled_start_time": "2026-10-05T10:00:00",
        "scheduled_end_time": "2026-10-05T11:00:00",
    }


def _assert_ten_local_or_seven_utc(value: str):
    assert value.startswith(("2026-10-05T10:00:00+03:00", "2026-10-05T07:00:00+00:00"))


def test_booking_http_constraints_and_time_round_trip(client, db_session, monkeypatch):
    customer, provider = _provider(db_session, client)
    _stub_booking_side_effects(monkeypatch)
    headers = customer["headers"]

    too_long = client.post(
        "/bookings",
        data=_form(provider.id, " ".join(["word"] * 31)),
        headers=headers,
    )
    assert too_long.status_code == 422

    too_many = client.post(
        "/bookings",
        data=_form(provider.id, "Valid title"),
        files=[("attachments", (f"{index}.jpg", b"x", "image/jpeg")) for index in range(6)],
        headers=headers,
    )
    assert too_many.status_code == 422

    created = client.post(
        "/bookings",
        data=_form(provider.id, "Valid title"),
        headers=headers,
    )
    assert created.status_code == 200, created.text
    booking_id = created.json()["data"]["booking"]["id"]
    _assert_ten_local_or_seven_utc(created.json()["data"]["booking"]["scheduled_start_time"])

    updated = client.put(
        f"/customer/bookings/{booking_id}",
        json={
            "title": "Updated title",
            "service_description": "Repair",
            "service_address": "Address",
            "service_latitude": 41,
            "service_longitude": 29,
            "scheduled_start_time": "2026-10-05T07:00:00+00:00",
            "scheduled_end_time": "2026-10-05T08:00:00+00:00",
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["booking"]["title"] == "Updated title"
    _assert_ten_local_or_seven_utc(updated.json()["data"]["booking"]["scheduled_start_time"])
