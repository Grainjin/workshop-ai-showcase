from sqlalchemy.orm import Session

from backend import models
from backend.schemas import BookingStatus, PaymentStatus, RefundRequestStatus

MAX_CONTEXT_ITEMS = 5

TOOL_TARGET_CONTEXT_MAP = {
    "prepare_pay_booking_action": {
        "target_field": "booking_id",
        "context_key": "awaiting_payment_can_pay",
    },
    "prepare_reject_quote_action": {
        "target_field": "booking_id",
        "context_key": "quoted_can_reject",
    },
    "prepare_cancel_booking_action": {
        "target_field": "booking_id",
        "context_key": "unpaid_can_cancel",
    },
    "prepare_refund_request_action": {
        "target_field": "booking_id",
        "context_key": "paid_can_request_refund",
    },
    "prepare_confirm_complete_action": {
        "target_field": "booking_id",
        "context_key": "awaiting_confirmation_can_confirm_or_reject",
    },
    "prepare_reject_complete_action": {
        "target_field": "booking_id",
        "context_key": "awaiting_confirmation_can_confirm_or_reject",
    },
    "prepare_quote_booking_action": {
        "target_field": "booking_id",
        "context_key": "pending_can_quote_or_reject",
    },
    "prepare_reject_booking_action": {
        "target_field": "booking_id",
        "context_key": "pending_can_quote_or_reject",
    },
    "prepare_complete_booking_action": {
        "target_field": "booking_id",
        "context_key": "accepted_can_complete",
    },
    "prepare_approve_refund_action": {
        "target_field": "refund_request_id",
        "context_key": "pending_refund_requests_can_approve_or_reject",
    },
    "prepare_reject_refund_action": {
        "target_field": "refund_request_id",
        "context_key": "pending_refund_requests_can_approve_or_reject",
    },
}


def format_ai_context_booking(booking: models.Booking):
    return {
        "booking_id": booking.id,
        "status": booking.status,
        "service_description": booking.service_description,
        "service_address": booking.service_address,
        "scheduled_start_time": booking.scheduled_start_time,
        "scheduled_end_time": booking.scheduled_end_time,
        "quote_amount": booking.quote_amount,
        "quote_message": booking.quote_message,
        "chat_room_id": booking.chat_room_id,
    }


def format_ai_context_refund_request(refund_request: models.RefundRequest):
    return {
        "refund_request_id": refund_request.id,
        "booking_id": refund_request.booking_id,
        "payment_id": refund_request.payment_id,
        "reason": refund_request.reason,
        "status": refund_request.status,
        "provider_note": refund_request.provider_note,
        "appeal_reason": refund_request.appeal_reason,
        "admin_note": refund_request.admin_note,
        "previous_booking_status": refund_request.previous_booking_status,
        "created_at": refund_request.created_at,
        "responded_at": refund_request.responded_at,
        "appealed_at": refund_request.appealed_at,
        "admin_responded_at": refund_request.admin_responded_at,
    }


def get_recent_bookings_by_status(
    db: Session,
    filters,
    statuses: list[BookingStatus],
):
    return (
        db.query(models.Booking)
        .filter(*filters, models.Booking.status.in_(statuses))
        .order_by(models.Booking.id.desc())
        .limit(MAX_CONTEXT_ITEMS)
        .all()
    )


def get_customer_refundable_bookings(user_id: int, db: Session):
    bookings = (
        db.query(models.Booking)
        .join(models.Payment, models.Payment.booking_id == models.Booking.id)
        .filter(
            models.Booking.customer_id == user_id,
            models.Booking.status == BookingStatus.completed,
            models.Payment.customer_id == user_id,
            models.Payment.status == PaymentStatus.paid,
        )
        .order_by(models.Booking.id.desc())
        .limit(MAX_CONTEXT_ITEMS)
        .all()
    )

    return [format_ai_context_booking(booking) for booking in bookings]


def build_customer_actionable_context(current_user: models.User, db: Session):
    base_filters = [models.Booking.customer_id == current_user.id]

    quoted_bookings = get_recent_bookings_by_status(
        db,
        base_filters,
        [BookingStatus.quoted],
    )
    awaiting_payment_bookings = get_recent_bookings_by_status(
        db,
        base_filters,
        [BookingStatus.awaiting_payment],
    )
    cancellable_bookings = get_recent_bookings_by_status(
        db,
        base_filters,
        [BookingStatus.pending, BookingStatus.quoted, BookingStatus.awaiting_payment],
    )
    completable_bookings = get_recent_bookings_by_status(
        db,
        base_filters,
        [BookingStatus.awaiting_confirmation],
    )

    return {
        "quoted_can_reject": [
            format_ai_context_booking(booking) for booking in quoted_bookings
        ],
        "awaiting_payment_can_pay": [
            format_ai_context_booking(booking) for booking in awaiting_payment_bookings
        ],
        "unpaid_can_cancel": [
            format_ai_context_booking(booking) for booking in cancellable_bookings
        ],
        "awaiting_confirmation_can_confirm_or_reject": [
            format_ai_context_booking(booking) for booking in completable_bookings
        ],
        "paid_can_request_refund": get_customer_refundable_bookings(
            current_user.id,
            db,
        ),
    }


def get_provider_profile_for_ai_context(current_user: models.User, db: Session):
    return (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.user_id == current_user.id)
        .first()
    )


def build_provider_refund_context(provider_profile_id: int, db: Session):
    refund_requests = (
        db.query(models.RefundRequest)
        .filter(
            models.RefundRequest.provider_profile_id == provider_profile_id,
            models.RefundRequest.status == RefundRequestStatus.pending,
        )
        .order_by(models.RefundRequest.id.desc())
        .limit(MAX_CONTEXT_ITEMS)
        .all()
    )

    results = []
    for refund_request in refund_requests:
        booking = (
            db.query(models.Booking)
            .filter(models.Booking.id == refund_request.booking_id)
            .first()
        )
        item = format_ai_context_refund_request(refund_request)
        item["booking"] = format_ai_context_booking(booking) if booking else None
        results.append(item)

    return results


def build_provider_actionable_context(current_user: models.User, db: Session):
    provider_profile = get_provider_profile_for_ai_context(current_user, db)
    if not provider_profile:
        return {
            "provider_profile_missing": True,
            "hint": "This provider has no profile yet and cannot perform booking actions.",
        }

    base_filters = [models.Booking.provider_profile_id == provider_profile.id]
    pending_bookings = get_recent_bookings_by_status(
        db,
        base_filters,
        [BookingStatus.pending],
    )
    accepted_bookings = get_recent_bookings_by_status(
        db,
        base_filters,
        [BookingStatus.accepted],
    )

    return {
        "provider_profile_id": provider_profile.id,
        "pending_can_quote_or_reject": [
            format_ai_context_booking(booking) for booking in pending_bookings
        ],
        "accepted_can_complete": [
            format_ai_context_booking(booking) for booking in accepted_bookings
        ],
        "pending_refund_requests_can_approve_or_reject": build_provider_refund_context(
            provider_profile.id,
            db,
        ),
    }


def build_ai_actionable_context(current_user: models.User, db: Session):
    if current_user.role == "customer":
        return build_customer_actionable_context(current_user, db)

    if current_user.role == "provider":
        return build_provider_actionable_context(current_user, db)

    return {}


def get_tool_target_context_config(tool_name: str | None):
    if not tool_name:
        return None

    return TOOL_TARGET_CONTEXT_MAP.get(tool_name)


def get_tool_target_choices(tool_name: str | None, actionable_context: dict):
    config = get_tool_target_context_config(tool_name)
    if not config:
        return []

    choices = actionable_context.get(config["context_key"]) or []

    return [
        {
            "index": index + 1,
            **choice,
        }
        for index, choice in enumerate(choices)
    ]


def build_pending_clarification_context(
    tool_name: str | None,
    tool_args: dict | None,
    missing_fields: list[str],
    actionable_context: dict,
):
    config = get_tool_target_context_config(tool_name)
    if not config or config["target_field"] not in missing_fields:
        return None

    choices = get_tool_target_choices(tool_name, actionable_context)
    if not choices:
        return None

    return {
        "tool_name": tool_name,
        "target_field": config["target_field"],
        "missing_fields": missing_fields,
        "original_tool_args": tool_args or {},
        "choices": choices,
        "instruction": (
            "If the user replies with first/second/1/2, fill original_tool_args with the matching choice target_field and retry tool_name."
        ),
    }
