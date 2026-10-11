"""Shared multi-role API.

Chat messages, notifications, booking details, attachments, status history.
Access depends on resource ownership, not just role.
"""

from datetime import datetime, timezone
from fastapi import Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from backend import models
from backend.auth import get_db, require_verified_user
from backend.utils.booking import (
    ensure_customer_owns_booking,
    format_booking_detail_response,
    get_booking_for_user_or_404,
)
from backend.utils.chat import (
    build_chat_attachment_metadata,
    dump_chat_message_metadata,
    ensure_chat_room_member,
    format_chat_message_response,
    format_chat_message_attachment_response,
    get_chat_message_recipient_user_id,
    get_chat_room_or_404,
    get_pending_chat_attachments_or_400,
    mark_chat_room_messages_as_read,
    register_chat_message_unread,
)
from backend.utils.formatters import format_booking_attachment_response
from backend.utils.notification import (
    create_notification,
    format_notification_response,
    get_notification_unread_count,
)
from backend.utils.pagination import build_paginated_response, paginate_query
from backend.utils.provider import get_provider_profile_for_user, require_provider_qualification_approved
from backend.services.redis_service import (
    decrement_notification_unread_count,
    set_notification_unread_count,
)
from backend.utils.upload import (
    delete_local_upload,
    save_booking_attachment_upload,
    save_chat_attachment_upload,
)
from backend.utils.websocket_manager import websocket_manager
from backend.schemas import (
    ApiResponse,
    BookingAttachmentResponse,
    ChatMessageCreate,
    ChatMessageAttachmentResponse,
    ChatMessageResponse,
    ChatMessageSendResponseData,
    ChatMessageType,
    NotificationRelatedType,
    NotificationType,
    PaginatedData,
)
from backend.utils.response import success_response
from backend.utils.router import ApiRouter
from backend.utils.demo_mode import reject_demo_restricted_action
from backend.core.clock import utc_now

router = ApiRouter(tags=["Shared"])


def _gate_provider_chat(current_user, chat_room, db):
    if current_user.role == "provider":
        profile = get_provider_profile_for_user(current_user.id, db)
        require_provider_qualification_approved(profile)


@router.get(
    "/chats/{chat_room_id}/messages",
    response_model=ApiResponse[PaginatedData[ChatMessageResponse]],
)
def get_chat_messages(
    chat_room_id: int,
    message_type: ChatMessageType | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    chat_room = get_chat_room_or_404(chat_room_id, db)
    ensure_chat_room_member(chat_room, current_user, db)
    _gate_provider_chat(current_user, chat_room, db)
    mark_chat_room_messages_as_read(chat_room, current_user, db)
    db.commit()

    query = db.query(models.ChatMessage).filter(
        models.ChatMessage.chat_room_id == chat_room.id
    )
    if message_type is not None:
        query = query.filter(models.ChatMessage.message_type == message_type.value)
    query = query.order_by(models.ChatMessage.created_at.desc())
    messages, total, page, page_size = paginate_query(query, page, page_size)
    messages.reverse()
    result = []
    for message in messages:
        result.append(format_chat_message_response(message, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.post(
    "/chats/{chat_room_id}/attachments",
    response_model=ApiResponse[ChatMessageAttachmentResponse],
)
async def upload_chat_attachment(
    chat_room_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "upload_chat_attachment")
    chat_room = get_chat_room_or_404(chat_room_id, db)
    ensure_chat_room_member(chat_room, current_user, db)
    _gate_provider_chat(current_user, chat_room, db)
    upload_result = await save_chat_attachment_upload(chat_room.id, file)
    attachment = models.ChatMessageAttachment(
        chat_room_id=chat_room.id,
        chat_message_id=None,
        uploaded_by_user_id=current_user.id,
        original_file_name=upload_result["original_file_name"],
        file_name=upload_result["file_name"],
        file_url=upload_result["file_url"],
        content_type=upload_result["content_type"],
        size=upload_result["size"],
        created_at=utc_now(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return success_response(
        format_chat_message_attachment_response(attachment),
        message="Chat attachment uploaded successfully",
    )


@router.delete(
    "/chats/{chat_room_id}/attachments/{attachment_id}",
    response_model=ApiResponse[None],
)
def delete_unsent_chat_attachment(
    chat_room_id: int,
    attachment_id: int,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    chat_room = get_chat_room_or_404(chat_room_id, db)
    ensure_chat_room_member(chat_room, current_user, db)
    _gate_provider_chat(current_user, chat_room, db)
    attachment = (
        db.query(models.ChatMessageAttachment)
        .filter(
            models.ChatMessageAttachment.id == attachment_id,
            models.ChatMessageAttachment.chat_room_id == chat_room.id,
        )
        .first()
    )

    if not attachment:
        raise HTTPException(status_code=404, detail="Chat attachment not found")

    if attachment.uploaded_by_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only delete attachments uploaded by yourself",
        )

    if attachment.chat_message_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Sent chat attachments cannot be deleted separately",
        )

    delete_local_upload(attachment.file_url)
    db.delete(attachment)
    db.commit()
    return success_response(message="Chat attachment deleted successfully")


@router.post(
    "/chats/{chat_room_id}/messages",
    response_model=ApiResponse[ChatMessageSendResponseData],
)
async def send_chat_message(
    chat_room_id: int,
    message_data: ChatMessageCreate,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    chat_room = get_chat_room_or_404(chat_room_id, db)
    ensure_chat_room_member(chat_room, current_user, db)
    _gate_provider_chat(current_user, chat_room, db)
    attachments = get_pending_chat_attachments_or_400(
        message_data.attachment_ids,
        chat_room,
        current_user,
        db,
    )
    now = utc_now()
    chat_message = models.ChatMessage(
        chat_room_id=chat_room.id,
        sender_id=current_user.id,
        message=message_data.message or "",
        message_type="attachment" if attachments else "text",
        related_type=None,
        related_id=None,
        metadata_json=(
            dump_chat_message_metadata(build_chat_attachment_metadata(attachments))
            if attachments
            else None
        ),
        created_at=now,
        read_at=None,
    )
    chat_room.last_message_at = now
    db.add(chat_message)
    db.flush()
    for attachment in attachments:
        attachment.chat_message_id = chat_message.id

    if current_user.role == "customer":
        provider_profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.id == chat_room.provider_profile_id)
            .first()
        )
        if provider_profile:
            notification_message = "A customer sent you a message"
            if attachments:
                notification_message = (
                    f"{notification_message} with {len(attachments)} attachment(s)"
                )
            create_notification(
                provider_profile.user_id,
                "New chat message",
                notification_message,
                NotificationType.chat_message_received,
                NotificationRelatedType.chat_room,
                chat_room.id,
                db,
            )
    if current_user.role == "provider":
        notification_message = "A provider sent you a message"
        if attachments:
            notification_message = (
                f"{notification_message} with {len(attachments)} attachment(s)"
            )
        create_notification(
            chat_room.customer_id,
            "New chat message",
            notification_message,
            NotificationType.chat_message_received,
            NotificationRelatedType.chat_room,
            chat_room.id,
            db,
        )
    db.commit()
    db.refresh(chat_message)
    db.refresh(chat_room)
    recipient_user_id = get_chat_message_recipient_user_id(chat_room, current_user, db)
    recipient_unread_count = register_chat_message_unread(
        chat_message,
        chat_room,
        recipient_user_id,
        db,
    )
    payload = {
        "type": "chat_message",
        "chat_room_id": chat_room.id,
        "chat_message": format_chat_message_response(chat_message, db),
    }
    await websocket_manager.send_to_user(current_user.id, {**payload, "unread_count": 0})
    if recipient_user_id:
        await websocket_manager.send_to_user(
            recipient_user_id,
            {**payload, "unread_count": recipient_unread_count},
        )
    return success_response(
        {
            "message": "Message sent successfully",
            "chat_message": format_chat_message_response(chat_message, db),
        }
    )


@router.get("/notifications")
def get_notifications(
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    )
    if unread_only:
        query = query.filter(models.Notification.read_at.is_(None))
    query = query.order_by(models.Notification.created_at.desc())
    notifications, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for notification in notifications:
        result.append(format_notification_response(notification, db, current_user))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/notifications/summary")
def get_notification_summary(
    current_user: models.User = Depends(require_verified_user), db: Session = Depends(get_db)
):
    unread_count = get_notification_unread_count(current_user.id, db)
    latest_notification = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == current_user.id)
        .order_by(models.Notification.created_at.desc())
        .first()
    )
    return success_response(
        {
            "unread_count": unread_count,
            "latest_notification": (
                format_notification_response(latest_notification, db, current_user)
                if latest_notification
                else None
            ),
        }
    )


@router.put("/notifications/read-all")
def mark_all_notifications_as_read(
    current_user: models.User = Depends(require_verified_user), db: Session = Depends(get_db)
):
    notifications = (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == current_user.id,
            models.Notification.read_at.is_(None),
        )
        .all()
    )
    now = utc_now()
    for notification in notifications:
        notification.read_at = now
    db.commit()
    set_notification_unread_count(current_user.id, 0)
    return success_response(
        {
            "message": "All notifications marked as read",
            "updated_count": len(notifications),
            "unread_count": 0,
        }
    )


@router.put("/notifications/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    notification = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    was_unread = notification.read_at is None
    if was_unread:
        notification.read_at = utc_now()
        db.commit()
        db.refresh(notification)
        decrement_notification_unread_count(current_user.id)
    unread_count = get_notification_unread_count(current_user.id, db)
    return success_response(
        {
            "message": "Notification marked as read",
            "unread_count": unread_count,
            "notification": format_notification_response(
                notification, db, current_user
            ),
        }
    )


@router.get("/chats/{chat_room_id}/bookings")
def get_chat_bookings(
    chat_room_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    chat_room = get_chat_room_or_404(chat_room_id, db)
    ensure_chat_room_member(chat_room, current_user, db)
    query = (
        db.query(models.Booking)
        .filter(models.Booking.chat_room_id == chat_room.id)
        .order_by(models.Booking.booking_at.desc())
    )
    bookings, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for booking in bookings:
        result.append(format_booking_detail_response(booking, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/bookings/{booking_id}")
def get_booking_by_id(
    booking_id: int,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if current_user.role == "admin":
        return success_response(
            format_booking_detail_response(
                booking, db, include_reference_price_range=True
            )
        )
    if current_user.role == "customer":
        if booking.customer_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You can only view your own bookings"
            )
        return success_response(
            format_booking_detail_response(
                booking, db, include_reference_price_range=True
            )
        )
    if current_user.role == "provider":
        provider_profile = get_provider_profile_for_user(current_user.id, db)
        if booking.provider_profile_id != provider_profile.id:
            raise HTTPException(
                status_code=403,
                detail="You can only view bookings for your provider profile",
            )
        return success_response(
            format_booking_detail_response(
                booking, db, include_reference_price_range=True
            )
        )
    raise HTTPException(
        status_code=403, detail="You do not have permission to view this booking"
    )


@router.post(
    "/bookings/{booking_id}/attachments",
    response_model=ApiResponse[BookingAttachmentResponse],
)
async def upload_booking_attachment(
    booking_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "upload_booking_attachment")
    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    ensure_customer_owns_booking(booking, current_user)
    upload_result = await save_booking_attachment_upload(booking.id, file)
    attachment = models.BookingAttachment(
        booking_id=booking.id,
        uploaded_by_user_id=current_user.id,
        purpose="customer_attachment",
        original_file_name=upload_result["original_file_name"],
        file_name=upload_result["file_name"],
        file_url=upload_result["file_url"],
        content_type=upload_result["content_type"],
        size=upload_result["size"],
        created_at=utc_now(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return success_response(
        format_booking_attachment_response(attachment),
        message="Booking attachment uploaded successfully",
    )


@router.get(
    "/bookings/{booking_id}/attachments",
    response_model=ApiResponse[PaginatedData[BookingAttachmentResponse]],
)
def get_booking_attachments(
    booking_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    query = (
        db.query(models.BookingAttachment)
        .filter(models.BookingAttachment.booking_id == booking.id)
        .order_by(models.BookingAttachment.created_at.desc())
    )
    attachments, total, page, page_size = paginate_query(query, page, page_size)
    result = [
        format_booking_attachment_response(attachment) for attachment in attachments
    ]
    return build_paginated_response(result, total, page, page_size)


@router.delete(
    "/bookings/{booking_id}/attachments/{attachment_id}",
    response_model=ApiResponse[None],
)
def delete_booking_attachment(
    booking_id: int,
    attachment_id: int,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    attachment = (
        db.query(models.BookingAttachment)
        .filter(
            models.BookingAttachment.id == attachment_id,
            models.BookingAttachment.booking_id == booking.id,
        )
        .first()
    )

    if not attachment:
        raise HTTPException(status_code=404, detail="Booking attachment not found")

    if attachment.uploaded_by_user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the uploader can delete this attachment",
        )

    delete_local_upload(attachment.file_url)
    db.delete(attachment)
    db.commit()
    return success_response(message="Booking attachment deleted successfully")


@router.get("/bookings/{booking_id}/history")
def get_booking_status_history(
    booking_id: int,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    get_booking_by_id(booking_id, current_user, db)
    query = (
        db.query(models.BookingStatusHistory)
        .filter(models.BookingStatusHistory.booking_id == booking_id)
        .order_by(models.BookingStatusHistory.changed_at.asc())
    )
    histories, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for history in histories:
        result.append(
            {
                "id": history.id,
                "booking_id": history.booking_id,
                "changed_by_user_id": history.changed_by_user_id,
                "old_status": history.old_status,
                "new_status": history.new_status,
                "note": history.note,
                "changed_at": history.changed_at,
            }
        )
    return success_response(build_paginated_response(result, total, page, page_size))
