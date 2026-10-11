from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.utils.formatters import (
    format_booking_attachment_response,
    format_booking_response,
    format_provider_profile_response,
    format_user_response,
)
from backend.schemas import BookingStatus, PaymentStatus, RefundRequestStatus
from backend.core.clock import utc_now

ADMIN_BOOKING_STATUS_TRANSITIONS = {
    BookingStatus.pending: [BookingStatus.quoted],
    BookingStatus.quoted: [BookingStatus.pending],
    BookingStatus.awaiting_payment: [BookingStatus.quoted],
    BookingStatus.accepted: [
        BookingStatus.awaiting_payment,
        BookingStatus.awaiting_confirmation,
    ],
    BookingStatus.awaiting_confirmation: [BookingStatus.accepted],
    BookingStatus.completed: [
        BookingStatus.accepted,
        BookingStatus.awaiting_confirmation,
    ],
    BookingStatus.refunding: [
        BookingStatus.completed,
    ],
    BookingStatus.refunded: [BookingStatus.refunding],
    BookingStatus.cancelled: [
        BookingStatus.pending,
        BookingStatus.quoted,
        BookingStatus.awaiting_payment,
    ],
    BookingStatus.rejected: [BookingStatus.pending],
}


def get_booking_or_404(booking_id: int, db: Session):
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    return booking


def can_user_access_booking(
    booking: models.Booking,
    current_user: models.User,
    db: Session,
):
    if current_user.role == "admin":
        return True

    if current_user.role == "customer":
        return booking.customer_id == current_user.id

    if current_user.role == "provider":
        provider_profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.user_id == current_user.id)
            .first()
        )
        return (
            provider_profile is not None
            and booking.provider_profile_id == provider_profile.id
        )

    return False


def get_booking_for_user_or_404(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    booking = get_booking_or_404(booking_id, db)

    if not can_user_access_booking(booking, current_user, db):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this booking",
        )

    return booking


def ensure_customer_owns_booking(
    booking: models.Booking,
    current_user: models.User,
):
    if current_user.role != "customer" or booking.customer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the customer who created this booking can upload attachments",
        )


def ensure_booking_status(
    booking: models.Booking, allowed_statuses: list[BookingStatus], detail: str
):
    if booking.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=detail,
        )


def get_booking_payment_by_status(
    booking: models.Booking,
    payment_status: PaymentStatus,
    db: Session,
):
    return (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.status == payment_status,
        )
        .first()
    )


def get_active_refund_request(booking: models.Booking, db: Session):
    return (
        db.query(models.RefundRequest)
        .filter(
            models.RefundRequest.booking_id == booking.id,
            models.RefundRequest.status.in_(
                [
                    RefundRequestStatus.pending,
                    RefundRequestStatus.rejected,
                    RefundRequestStatus.appealed,
                ]
            ),
        )
        .first()
    )


def ensure_admin_booking_status_update_allowed(
    booking: models.Booking,
    new_status: BookingStatus,
    db: Session,
):
    if booking.status == new_status:
        raise HTTPException(
            status_code=400,
            detail="Booking is already in this status",
        )

    allowed_previous_statuses = ADMIN_BOOKING_STATUS_TRANSITIONS.get(new_status)

    if (
        allowed_previous_statuses is not None
        and booking.status not in allowed_previous_statuses
    ):
        raise HTTPException(
            status_code=400,
            detail="Admin status update is not allowed for this transition",
        )

    if new_status == BookingStatus.quoted and booking.quote_amount is None:
        raise HTTPException(
            status_code=400,
            detail="Booking cannot be set to quoted without a quote amount",
        )

    if new_status in [
        BookingStatus.accepted,
        BookingStatus.awaiting_confirmation,
        BookingStatus.completed,
    ]:
        paid_payment = get_booking_payment_by_status(
            booking,
            PaymentStatus.paid,
            db,
        )

        if not paid_payment:
            raise HTTPException(
                status_code=400,
                detail="Booking cannot move to paid work status without a paid payment",
            )

    if new_status == BookingStatus.awaiting_confirmation:
        ensure_booking_status(
            booking,
            [BookingStatus.accepted],
            "Only accepted bookings can move to awaiting confirmation",
        )

    if new_status == BookingStatus.completed:
        ensure_booking_status(
            booking,
            [BookingStatus.accepted, BookingStatus.awaiting_confirmation],
            "Only accepted bookings can be completed",
        )

    if new_status == BookingStatus.refunding and not get_active_refund_request(
        booking,
        db,
    ):
        raise HTTPException(
            status_code=400,
            detail="Booking cannot move to refunding without an active refund request",
        )

    if new_status == BookingStatus.refunded:
        refunded_payment = get_booking_payment_by_status(
            booking,
            PaymentStatus.refunded,
            db,
        )

        if not refunded_payment:
            raise HTTPException(
                status_code=400,
                detail="Booking cannot be refunded without a refunded payment",
            )


def save_booking(booking: models.Booking, db: Session):
    db.commit()
    db.refresh(booking)

    return {
        "booking": format_booking_response(booking),
    }


def add_booking_status_history(
    booking: models.Booking,
    old_status: str,
    new_status: str,
    note: str | None,
    current_user: models.User,
    db: Session,
):
    history = models.BookingStatusHistory(
        booking_id=booking.id,
        changed_by_user_id=current_user.id,
        old_status=old_status,
        new_status=new_status,
        note=note,
        changed_at=utc_now(),
    )

    db.add(history)


def get_booking_complaint_summary(booking: models.Booking, db: Session):
    total_complaint_count = (
        db.query(models.Complaint)
        .filter(models.Complaint.booking_id == booking.id)
        .count()
    )
    open_complaint_count = (
        db.query(models.Complaint)
        .filter(
            models.Complaint.booking_id == booking.id,
            models.Complaint.status == "open",
        )
        .count()
    )

    return {
        "has_open_complaint": open_complaint_count > 0,
        "open_complaint_count": open_complaint_count,
        "total_complaint_count": total_complaint_count,
    }


def get_booking_current_refund_request_summary(booking: models.Booking, db: Session):
    refund_request = (
        db.query(models.RefundRequest)
        .filter(models.RefundRequest.booking_id == booking.id)
        .order_by(models.RefundRequest.created_at.desc())
        .first()
    )
    if not refund_request:
        return None

    return {
        "id": refund_request.id,
        "booking_id": refund_request.booking_id,
        "payment_id": refund_request.payment_id,
        "customer_id": refund_request.customer_id,
        "provider_profile_id": refund_request.provider_profile_id,
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
        "cancelled_at": refund_request.cancelled_at,
        "refunded_at": refund_request.refunded_at,
        "refund_amount": refund_request.refund_amount,
    }


def get_booking_last_declined_quote(booking: models.Booking, db: Session):
    revision = (
        db.query(models.BookingQuoteRevision)
        .filter(
            models.BookingQuoteRevision.booking_id == booking.id,
            models.BookingQuoteRevision.declined_at.isnot(None),
        )
        .order_by(models.BookingQuoteRevision.revision_number.desc())
        .first()
    )
    if not revision:
        return None

    return {
        "revision_number": revision.revision_number,
        "quote_amount": revision.quote_amount,
        "expected_service_amount": revision.expected_service_amount,
        "visit_fee_amount": revision.visit_fee_amount,
        "total_amount": revision.total_amount,
        "quote_message": revision.quote_message,
        "declined_at": revision.declined_at,
        "decline_reason": revision.decline_reason,
    }


def get_booking_last_declined_final_quote(booking: models.Booking, db: Session):
    revision = (
        db.query(models.BookingQuoteRevision)
        .filter(
            models.BookingQuoteRevision.booking_id == booking.id,
            models.BookingQuoteRevision.declined_at.isnot(None),
            models.BookingQuoteRevision.expected_service_amount.is_(None),
            models.BookingQuoteRevision.visit_fee_amount.is_(None),
        )
        .order_by(models.BookingQuoteRevision.revision_number.desc())
        .first()
    )
    if not revision:
        return None

    return {
        "revision_number": revision.revision_number,
        "quote_amount": revision.quote_amount,
        "quote_message": revision.quote_message,
        "visit_fee_amount": booking.visit_fee_amount,
        "declined_at": revision.declined_at,
        "decline_reason": revision.decline_reason,
    }


def format_booking_detail_response(
    booking: models.Booking,
    db: Session,
    *,
    include_reference_price_range: bool = False,
):
    result = format_booking_response(booking)

    latest_payment = db.query(models.Payment).filter_by(booking_id=booking.id).order_by(
        models.Payment.created_at.desc(), models.Payment.id.desc(),
    ).first()
    result["payment_method"] = latest_payment.payment_method if latest_payment else None

    if include_reference_price_range:
        from backend.utils.reference_price import calculate_reference_price_range

        result["reference_price_range"] = calculate_reference_price_range(booking, db)

    customer = (
        db.query(models.User).filter(models.User.id == booking.customer_id).first()
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )

    result["customer"] = format_user_response(customer) if customer else None
    result["provider"] = (
        format_provider_profile_response(provider_profile) if provider_profile else None
    )
    attachments = (
        db.query(models.BookingAttachment)
        .filter(models.BookingAttachment.booking_id == booking.id)
        .order_by(models.BookingAttachment.created_at.desc())
        .all()
    )
    result["attachments"] = [
        format_booking_attachment_response(attachment) for attachment in attachments
    ]
    result["complaint_summary"] = get_booking_complaint_summary(booking, db)
    result["current_refund_request"] = get_booking_current_refund_request_summary(
        booking,
        db,
    )
    result["last_declined_quote"] = get_booking_last_declined_quote(booking, db)
    result["last_declined_final_quote"] = get_booking_last_declined_final_quote(
        booking, db
    )
    latest_quote_revision = (
        db.query(models.BookingQuoteRevision)
        .filter(models.BookingQuoteRevision.booking_id == booking.id)
        .order_by(models.BookingQuoteRevision.revision_number.desc())
        .first()
    )
    result["current_quote_revision_id"] = (
        latest_quote_revision.id
        if latest_quote_revision and latest_quote_revision.declined_at is None
        else None
    )

    return result
