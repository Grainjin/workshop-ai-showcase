from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend import models
from backend.utils.booking import format_booking_detail_response
from backend.utils.chat import format_chat_message_response
from backend.utils.formatters import format_user_response
from backend.core.clock import utc_now


def add_complaint_status_history(
    complaint: models.Complaint,
    old_status: str,
    new_status: str,
    note: str | None,
    current_user: models.User,
    db: Session,
):
    history = models.ComplaintStatusHistory(
        complaint_id=complaint.id,
        changed_by_user_id=current_user.id,
        old_status=old_status,
        new_status=new_status,
        note=note,
        changed_at=utc_now(),
    )

    db.add(history)


def format_complaint_response(
    complaint: models.Complaint,
    db: Session,
    include_chat_messages: bool = False,
):
    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == complaint.booking_id)
        .first()
    )
    customer = (
        db.query(models.User).filter(models.User.id == complaint.customer_id).first()
    )

    result = {
        "id": complaint.id,
        "booking_id": complaint.booking_id,
        "customer_id": complaint.customer_id,
        "reason": complaint.reason,
        "status": complaint.status,
        "admin_note": complaint.admin_note,
        "created_at": complaint.created_at,
        "resolved_at": complaint.resolved_at,
        "customer": format_user_response(customer) if customer else None,
        "booking": format_booking_detail_response(booking, db) if booking else None,
    }

    if include_chat_messages and booking and booking.chat_room_id:
        messages = (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.chat_room_id == booking.chat_room_id)
            .order_by(models.ChatMessage.created_at.asc())
            .all()
        )

        result["chat_messages"] = []

        for message in messages:
            result["chat_messages"].append(format_chat_message_response(message, db))

    return result
