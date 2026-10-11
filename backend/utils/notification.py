from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend import models
from backend.schemas import NotificationRelatedType, NotificationType
from backend.services.redis_service import (
    increment_notification_unread_count,
    set_notification_unread_count,
)
from backend.utils.notification_queue import enqueue_notification_delivery
from backend.utils.booking import format_booking_detail_response
from backend.utils.chat import format_chat_room_response
from backend.utils.complaint import format_complaint_response
from backend.utils.payment import format_payment_response
from backend.utils.refund import format_refund_request_response
from backend.utils.formatters import format_provider_portfolio_response
from backend.utils.provider import format_provider_profile_with_rating
from backend.core.clock import utc_now


def create_notification(
    user_id: int,
    title: str,
    content: str,
    notification_type: NotificationType,
    related_type: NotificationRelatedType,
    related_id: int,
    db: Session,
):
    notification = models.Notification(
        user_id=user_id,
        title=title,
        content=content,
        notification_type=notification_type.value,
        related_type=related_type.value,
        related_id=related_id,
        read_at=None,
        created_at=utc_now(),
    )

    db.add(notification)
    increment_notification_unread_count(user_id)
    enqueue_notification_delivery(
        user_id,
        title,
        content,
        notification_type.value,
        related_type.value,
        related_id,
        db,
    )
    return notification


def count_unread_notifications_from_db(user_id: int, db: Session):
    return (
        db.query(models.Notification)
        .filter(
            models.Notification.user_id == user_id,
            models.Notification.read_at.is_(None),
        )
        .count()
    )


def get_notification_unread_count(user_id: int, db: Session):
    unread_count = count_unread_notifications_from_db(user_id, db)
    set_notification_unread_count(user_id, unread_count)
    return unread_count


def create_admin_notifications(
    title: str,
    content: str,
    notification_type: NotificationType,
    related_type: NotificationRelatedType,
    related_id: int,
    db: Session,
):
    admins = db.query(models.User).filter(models.User.role == "admin").all()

    for admin in admins:
        create_notification(
            admin.id,
            title,
            content,
            notification_type,
            related_type,
            related_id,
            db,
        )


def get_provider_user_id(provider_profile_id: int, db: Session):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == provider_profile_id)
        .first()
    )

    return provider_profile.user_id if provider_profile else None


def can_view_booking_related_data(
    booking: models.Booking,
    current_user: models.User | None,
    db: Session,
):
    if current_user is None:
        return True

    if current_user.role == "admin":
        return True

    if current_user.role == "customer":
        return booking.customer_id == current_user.id

    if current_user.role == "provider":
        provider_user_id = get_provider_user_id(
            booking.provider_profile_id,
            db,
        )
        return provider_user_id == current_user.id

    return False


def can_view_chat_room_related_data(
    chat_room: models.ChatRoom,
    current_user: models.User | None,
    db: Session,
):
    if current_user is None:
        return True

    if current_user.role == "admin":
        return True

    if current_user.role == "customer":
        return chat_room.customer_id == current_user.id

    if current_user.role == "provider":
        provider_user_id = get_provider_user_id(
            chat_room.provider_profile_id,
            db,
        )
        return provider_user_id == current_user.id

    return False


def can_view_complaint_related_data(
    complaint: models.Complaint,
    current_user: models.User | None,
    db: Session,
):
    if current_user is None:
        return True

    if current_user.role == "admin":
        return True

    if current_user.role == "customer":
        return complaint.customer_id == current_user.id

    if current_user.role == "provider":
        booking = (
            db.query(models.Booking)
            .filter(models.Booking.id == complaint.booking_id)
            .first()
        )

        return (
            can_view_booking_related_data(booking, current_user, db)
            if booking
            else False
        )

    return False


def can_view_payment_related_data(
    payment: models.Payment,
    current_user: models.User | None,
    db: Session,
):
    if current_user is None:
        return True

    if current_user.role == "admin":
        return True

    if current_user.role == "customer":
        return payment.customer_id == current_user.id

    if current_user.role == "provider":
        provider_user_id = get_provider_user_id(
            payment.provider_profile_id,
            db,
        )
        return provider_user_id == current_user.id

    return False


def can_view_refund_request_related_data(
    refund_request: models.RefundRequest,
    current_user: models.User | None,
    db: Session,
):
    if current_user is None:
        return True

    if current_user.role == "admin":
        return True

    if current_user.role == "customer":
        return refund_request.customer_id == current_user.id

    if current_user.role == "provider":
        provider_user_id = get_provider_user_id(
            refund_request.provider_profile_id,
            db,
        )
        return provider_user_id == current_user.id

    return False


def get_notification_related_data(
    notification: models.Notification,
    db: Session,
    current_user: models.User | None = None,
):
    if notification.related_type == NotificationRelatedType.booking.value:
        booking = (
            db.query(models.Booking)
            .filter(models.Booking.id == notification.related_id)
            .first()
        )

        if booking and not can_view_booking_related_data(booking, current_user, db):
            return None

        return format_booking_detail_response(booking, db) if booking else None

    if notification.related_type == NotificationRelatedType.chat_room.value:
        chat_room = (
            db.query(models.ChatRoom)
            .filter(models.ChatRoom.id == notification.related_id)
            .first()
        )

        if chat_room and not can_view_chat_room_related_data(
            chat_room,
            current_user,
            db,
        ):
            return None

        return format_chat_room_response(chat_room, db) if chat_room else None

    if notification.related_type == NotificationRelatedType.complaint.value:
        complaint = (
            db.query(models.Complaint)
            .filter(models.Complaint.id == notification.related_id)
            .first()
        )

        if complaint and not can_view_complaint_related_data(
            complaint,
            current_user,
            db,
        ):
            return None

        return format_complaint_response(complaint, db) if complaint else None

    if notification.related_type == NotificationRelatedType.payment.value:
        payment = (
            db.query(models.Payment)
            .filter(models.Payment.id == notification.related_id)
            .first()
        )

        if payment and not can_view_payment_related_data(payment, current_user, db):
            return None

        return format_payment_response(payment, db) if payment else None

    if notification.related_type == NotificationRelatedType.refund_request.value:
        refund_request = (
            db.query(models.RefundRequest)
            .filter(models.RefundRequest.id == notification.related_id)
            .first()
        )

        if refund_request and not can_view_refund_request_related_data(
            refund_request,
            current_user,
            db,
        ):
            return None

        return (
            format_refund_request_response(refund_request, db)
            if refund_request
            else None
        )

    if notification.related_type == NotificationRelatedType.provider_portfolio.value:
        portfolio = (
            db.query(models.ProviderPortfolio)
            .filter(models.ProviderPortfolio.id == notification.related_id)
            .first()
        )

        return format_provider_portfolio_response(portfolio, db) if portfolio else None

    if notification.related_type == NotificationRelatedType.provider_profile.value:
        profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.id == notification.related_id)
            .first()
        )

        return format_provider_profile_with_rating(profile, db) if profile else None

    return None


def format_notification_response(
    notification: models.Notification,
    db: Session | None = None,
    current_user: models.User | None = None,
):
    result = {
        "id": notification.id,
        "user_id": notification.user_id,
        "title": notification.title,
        "content": notification.content,
        "notification_type": notification.notification_type,
        "related_type": notification.related_type,
        "related_id": notification.related_id,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
    }

    if db is not None:
        result["related_data"] = get_notification_related_data(
            notification,
            db,
            current_user,
        )

    return result
