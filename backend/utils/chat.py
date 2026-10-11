import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.services.redis_service import (
    clear_chat_room_unread_count,
    get_cached_chat_room_unread_count,
    increment_chat_room_unread_count,
    is_user_online,
    set_chat_room_unread_count,
)
from backend.core.serialize import jsonable
from backend.utils.formatters import format_user_response
from backend.utils.provider import format_provider_profile_with_rating
from backend.utils.websocket_manager import websocket_manager
from backend.core.clock import utc_now


def get_or_create_chat_room(
    customer_id: int,
    provider_profile_id: int,
    db: Session,
):
    chat_room = (
        db.query(models.ChatRoom)
        .filter(
            models.ChatRoom.customer_id == customer_id,
            models.ChatRoom.provider_profile_id == provider_profile_id,
        )
        .first()
    )

    if chat_room:
        return chat_room

    chat_room = models.ChatRoom(
        customer_id=customer_id,
        provider_profile_id=provider_profile_id,
        created_at=utc_now(),
        last_message_at=None,
    )

    db.add(chat_room)
    db.flush()

    return chat_room


def create_booking_chat_message(
    chat_room: models.ChatRoom,
    booking: models.Booking,
    sender_id: int,
    db: Session,
    attachments: list[models.BookingAttachment] | None = None,
):
    now = utc_now()
    attachment_line = ""
    if attachments:
        attachment_names = ", ".join(
            attachment.original_file_name for attachment in attachments[:5]
        )
        if len(attachments) > 5:
            attachment_names = f"{attachment_names}, ..."
        attachment_line = f"\nAttachments: {attachment_names}"

    message = (
        f"[Booking Request]\n"
        f"Booking ID: {booking.id}\n"
        f"Service: {booking.service_description}\n"
        f"Scheduled time: {booking.scheduled_start_time} - {booking.scheduled_end_time}\n"
        f"Status: {booking.status}"
        f"{attachment_line}"
    )
    metadata = {
        "booking_id": booking.id,
        "provider_profile_id": booking.provider_profile_id,
        "service_description": booking.service_description,
        "service_address": booking.service_address,
        "service_latitude": booking.service_latitude,
        "service_longitude": booking.service_longitude,
        "scheduled_start_time": booking.scheduled_start_time,
        "scheduled_end_time": booking.scheduled_end_time,
        "status": booking.status,
        "attachment_count": len(attachments or []),
        "attachments": [
            {
                "id": attachment.id,
                "original_file_name": attachment.original_file_name,
                "file_url": attachment.file_url,
                "content_type": attachment.content_type,
                "size": attachment.size,
            }
            for attachment in attachments or []
        ],
    }
    chat_message = models.ChatMessage(
        chat_room_id=chat_room.id,
        sender_id=sender_id,
        message=message,
        message_type="booking_created",
        related_type="booking",
        related_id=booking.id,
        metadata_json=dump_chat_message_metadata(metadata),
        created_at=now,
        read_at=None,
    )
    chat_room.last_message_at = now

    db.add(chat_message)

    return chat_message


def create_booking_status_chat_message(
    booking: models.Booking,
    old_status: str,
    sender_id: int,
    title: str,
    detail: str | None,
    db: Session,
    metadata: dict | None = None,
):
    if booking.chat_room_id is None:
        return None

    chat_room = (
        db.query(models.ChatRoom)
        .filter(models.ChatRoom.id == booking.chat_room_id)
        .first()
    )
    if not chat_room:
        return None

    now = utc_now()
    message_parts = [
        "[Booking Status]",
        f"Booking ID: {booking.id}",
        f"Status: {old_status} -> {booking.status}",
        title,
    ]
    if detail:
        message_parts.append(f"Note: {detail}")
    message_metadata = {
        "booking_id": booking.id,
        "old_status": old_status,
        "new_status": booking.status,
        "title": title,
        "detail": detail,
    }
    if metadata:
        message_metadata.update(metadata)
    # Keep the current quote split on every booking update. This lets the
    # chat card show the payable visit fee even when the latest update was
    # created by an accept/payment action that only supplied payment fields.
    message_metadata.update(
        {
            "quote_amount": booking.quote_amount,
            "expected_service_amount": booking.expected_service_amount,
            "visit_fee_amount": booking.visit_fee_amount,
            "final_quote_amount": booking.final_quote_amount,
            "final_quote_message": booking.final_quote_message,
            "quote_message": booking.quote_message,
        }
    )

    chat_message = models.ChatMessage(
        chat_room_id=chat_room.id,
        sender_id=sender_id,
        message="\n".join(message_parts),
        message_type="booking_status",
        related_type="booking",
        related_id=booking.id,
        metadata_json=dump_chat_message_metadata(message_metadata),
        created_at=now,
        read_at=None,
    )
    chat_room.last_message_at = now
    db.add(chat_message)
    db.flush()

    return chat_message


def dump_chat_message_metadata(metadata: dict | None):
    if metadata is None:
        return None

    return json.dumps(jsonable(metadata), ensure_ascii=False)


def build_chat_attachment_metadata(attachments: list[models.ChatMessageAttachment]):
    if not attachments:
        return None

    return {
        "attachment_count": len(attachments),
        "attachment_types": sorted(
            {attachment.content_type for attachment in attachments}
        ),
        "attachments": [
            {
                "id": attachment.id,
                "original_file_name": attachment.original_file_name,
                "file_url": attachment.file_url,
                "content_type": attachment.content_type,
                "size": attachment.size,
            }
            for attachment in attachments
        ],
    }


def load_chat_message_metadata(metadata_json: str | None):
    if not metadata_json:
        return None

    try:
        return json.loads(metadata_json)
    except json.JSONDecodeError:
        return None


async def push_chat_message_to_room_members(
    chat_message: models.ChatMessage | None,
    db: Session,
):
    if chat_message is None:
        return

    chat_room = (
        db.query(models.ChatRoom)
        .filter(models.ChatRoom.id == chat_message.chat_room_id)
        .first()
    )
    if not chat_room:
        return

    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == chat_room.provider_profile_id)
        .first()
    )
    recipient_user_ids = {chat_room.customer_id}
    if provider_profile:
        recipient_user_ids.add(provider_profile.user_id)

    for user_id in recipient_user_ids:
        unread_count = 0
        if user_id != chat_message.sender_id:
            unread_count = increment_chat_room_unread_count(user_id, chat_room.id)
            if unread_count is None:
                unread_count = count_chat_room_unread_from_db(
                    chat_room,
                    user_id,
                    db,
                )
                set_chat_room_unread_count(user_id, chat_room.id, unread_count)

        payload = {
            "type": "chat_message",
            "chat_room_id": chat_room.id,
            "chat_message": format_chat_message_response(chat_message, db),
            "unread_count": unread_count,
        }
        await websocket_manager.send_to_user(user_id, payload)


def count_chat_room_unread_from_db(
    chat_room: models.ChatRoom,
    user_id: int,
    db: Session,
):
    return (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.chat_room_id == chat_room.id,
            models.ChatMessage.sender_id != user_id,
            models.ChatMessage.read_at.is_(None),
        )
        .count()
    )


def get_chat_room_unread_count(
    chat_room: models.ChatRoom,
    current_user: models.User,
    db: Session,
):
    cached_count = get_cached_chat_room_unread_count(current_user.id, chat_room.id)
    if cached_count is not None:
        return cached_count

    unread_count = count_chat_room_unread_from_db(chat_room, current_user.id, db)
    set_chat_room_unread_count(current_user.id, chat_room.id, unread_count)

    return unread_count


def register_chat_message_unread(
    chat_message: models.ChatMessage,
    chat_room: models.ChatRoom,
    recipient_user_id: int | None,
    db: Session,
):
    if not recipient_user_id or recipient_user_id == chat_message.sender_id:
        return 0

    unread_count = increment_chat_room_unread_count(
        recipient_user_id,
        chat_room.id,
    )
    if unread_count is None:
        unread_count = count_chat_room_unread_from_db(
            chat_room,
            recipient_user_id,
            db,
        )
        set_chat_room_unread_count(recipient_user_id, chat_room.id, unread_count)

    return unread_count


def mark_chat_room_messages_as_read(
    chat_room: models.ChatRoom,
    current_user: models.User,
    db: Session,
):
    unread_messages = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.chat_room_id == chat_room.id,
            models.ChatMessage.sender_id != current_user.id,
            models.ChatMessage.read_at.is_(None),
        )
        .all()
    )

    read_at = utc_now()
    message_ids = []
    for message in unread_messages:
        message.read_at = read_at
        message_ids.append(message.id)

    clear_chat_room_unread_count(current_user.id, chat_room.id)

    return {
        "updated_count": len(message_ids),
        "message_ids": message_ids,
        "read_at": read_at,
        "unread_count": 0,
    }


def format_chat_room_response(
    chat_room: models.ChatRoom,
    db: Session,
):
    customer = (
        db.query(models.User).filter(models.User.id == chat_room.customer_id).first()
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == chat_room.provider_profile_id)
        .first()
    )
    provider_user_id = provider_profile.user_id if provider_profile else None
    last_message = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.chat_room_id == chat_room.id)
        .order_by(models.ChatMessage.created_at.desc())
        .first()
    )

    return jsonable({
        "id": chat_room.id,
        "customer_id": chat_room.customer_id,
        "provider_profile_id": chat_room.provider_profile_id,
        "created_at": chat_room.created_at,
        "last_message_at": chat_room.last_message_at,
        "customer": format_user_response(customer) if customer else None,
        "customer_online": is_user_online(chat_room.customer_id),
        "provider": (
            format_provider_profile_with_rating(provider_profile, db)
            if provider_profile
            else None
        ),
        "provider_online": (
            is_user_online(provider_user_id) if provider_user_id else False
        ),
        "last_message": (
            format_chat_message_response(last_message, db) if last_message else None
        ),
    })


def format_chat_room_response_with_unread(
    chat_room: models.ChatRoom,
    db: Session,
    current_user: models.User,
):
    result = format_chat_room_response(chat_room, db)
    result["unread_count"] = get_chat_room_unread_count(
        chat_room,
        current_user,
        db,
    )
    return result


def format_chat_message_response(chat_message: models.ChatMessage, db: Session):
    sender = (
        db.query(models.User).filter(models.User.id == chat_message.sender_id).first()
    )
    attachments = (
        db.query(models.ChatMessageAttachment)
        .filter(models.ChatMessageAttachment.chat_message_id == chat_message.id)
        .order_by(models.ChatMessageAttachment.created_at.asc())
        .all()
    )

    return jsonable({
        "id": chat_message.id,
        "chat_room_id": chat_message.chat_room_id,
        "sender_id": chat_message.sender_id,
        "sender": format_user_response(sender) if sender else None,
        "message": chat_message.message,
        "message_type": chat_message.message_type,
        "related_type": chat_message.related_type,
        "related_id": chat_message.related_id,
        "metadata": load_chat_message_metadata(chat_message.metadata_json),
        "attachments": [
            format_chat_message_attachment_response(attachment)
            for attachment in attachments
        ],
        "created_at": chat_message.created_at,
        "read_at": chat_message.read_at,
    })


def format_chat_message_attachment_response(attachment: models.ChatMessageAttachment):
    return {
        "id": attachment.id,
        "chat_room_id": attachment.chat_room_id,
        "chat_message_id": attachment.chat_message_id,
        "uploaded_by_user_id": attachment.uploaded_by_user_id,
        "original_file_name": attachment.original_file_name,
        "file_name": attachment.file_name,
        "file_url": attachment.file_url,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "created_at": attachment.created_at,
    }


def get_pending_chat_attachments_or_400(
    attachment_ids: list[int],
    chat_room: models.ChatRoom,
    current_user: models.User,
    db: Session,
):
    unique_attachment_ids = list(dict.fromkeys(attachment_ids))

    if not unique_attachment_ids:
        return []

    attachments = (
        db.query(models.ChatMessageAttachment)
        .filter(models.ChatMessageAttachment.id.in_(unique_attachment_ids))
        .all()
    )

    if len(attachments) != len(unique_attachment_ids):
        raise HTTPException(status_code=404, detail="Chat attachment not found")

    for attachment in attachments:
        if attachment.chat_room_id != chat_room.id:
            raise HTTPException(
                status_code=400,
                detail="Attachment does not belong to this chat room",
            )

        if attachment.uploaded_by_user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only send attachments uploaded by yourself",
            )

        if attachment.chat_message_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Attachment has already been sent in a message",
            )

    return attachments


def get_chat_message_recipient_user_id(
    chat_room: models.ChatRoom,
    current_user: models.User,
    db: Session,
):
    if current_user.role == "customer":
        provider_profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.id == chat_room.provider_profile_id)
            .first()
        )

        return provider_profile.user_id if provider_profile else None

    if current_user.role == "provider":
        return chat_room.customer_id

    return None


def get_chat_room_or_404(chat_room_id: int, db: Session):
    chat_room = (
        db.query(models.ChatRoom).filter(models.ChatRoom.id == chat_room_id).first()
    )

    if not chat_room:
        raise HTTPException(
            status_code=404,
            detail="Chat room not found",
        )

    return chat_room


def ensure_chat_room_member(
    chat_room: models.ChatRoom,
    current_user: models.User,
    db: Session,
):
    if current_user.role == "customer" and chat_room.customer_id == current_user.id:
        return

    if current_user.role == "provider":
        provider_profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.user_id == current_user.id)
            .first()
        )

        if provider_profile and chat_room.provider_profile_id == provider_profile.id:
            return

    raise HTTPException(
        status_code=403,
        detail="You do not have permission to access this chat",
    )
