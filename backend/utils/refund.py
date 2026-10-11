from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import config, models
from backend.services.demo_payment import complete_demo_refund
from backend.schemas import BookingStatus
from backend.utils.booking import format_booking_detail_response
from backend.utils.payment import format_payment_response
from backend.core.clock import utc_now
from backend.services import iyzico as iyzico_service

REFUND_RESTORABLE_BOOKING_STATUSES = [
    BookingStatus.provider_arrived,
    BookingStatus.awaiting_final_quote,
    BookingStatus.final_quote_sent,
    BookingStatus.awaiting_service_payment,
    BookingStatus.service_paid,
    BookingStatus.awaiting_confirmation,
    BookingStatus.completed,
]


async def execute_external_refund(
    payment: models.Payment,
    refund_request: models.RefundRequest,
    db: Session,
) -> str:
    """Execute the one external money movement for a refund request.

    An authorized payment is released with Cancel/Void; a captured payment is
    refunded by transaction ID. Local terminal states are only written after
    iyzico confirms success, so an approval can safely retry the same request.
    """
    if payment.payment_method == "demo":
        simulated = complete_demo_refund(payment, refund_request.refund_amount, db)
        return _apply_refund_result(payment, refund_request, db, "refunded", simulated.refund_id)
    if config.PAYMENT_MODE == "demo" or config.DEMO_MODE:
        raise HTTPException(status_code=403, detail="External refunds are disabled in demo mode")
    client = iyzico_service.get_iyzico_client()
    try:
        if payment.status == "authorized":
            if not payment.iyzico_payment_id or not payment.conversation_id:
                raise HTTPException(status_code=409, detail="Authorized payment reference is missing")
            result = await client.cancel_payment(
                payment.iyzico_payment_id, payment.conversation_id
            )
            movement = "voided"
        elif payment.status in {"paid", "partially_refunded"}:
            if not payment.payment_transaction_id or not payment.conversation_id:
                raise HTTPException(status_code=409, detail="Payment transaction reference is missing")
            result = await client.refund_payment(
                payment.payment_transaction_id,
                payment.conversation_id,
                refund_request.refund_amount,
            )
            movement = "refunded"
        else:
            raise HTTPException(status_code=409, detail="Payment cannot be refunded in its current state")
    except iyzico_service.IyzicoClientError as exc:
        response_data = exc.response_data or {}
        refund_request.failure_code = str(response_data.get("errorCode") or "refund_failed")
        refund_request.failure_message = str(response_data.get("errorMessage") or str(exc))
        db.commit()
        raise HTTPException(status_code=502, detail=refund_request.failure_message) from exc

    if str(result.get("status", "")).lower() != "success":
        refund_request.failure_code = str(result.get("errorCode") or "refund_failed")
        refund_request.failure_message = str(
            result.get("errorMessage") or "iyzico rejected the refund"
        )
        db.commit()
        raise HTTPException(status_code=502, detail=refund_request.failure_message)

    external_refund_id = str(
        result.get("paymentId")
        or result.get("paymentTransactionId")
        or result.get("conversationId")
        or ""
    ) or None
    return _apply_refund_result(payment, refund_request, db, movement, external_refund_id)


def _apply_refund_result(payment, refund_request, db, movement, external_refund_id):
    refund_request.failure_code = None
    refund_request.failure_message = None
    refund_request.external_refund_id = external_refund_id
    if movement == "voided":
        payment.status = "voided"
        payment.voided_at = utc_now()
        payment.external_status = "voided"
    else:
        is_full = refund_request.refund_amount >= payment.amount
        payment.status = "refunded" if is_full else "partially_refunded"
        payment.refunded_at = utc_now()
        payment.external_status = "simulated" if payment.payment_method == "demo" else payment.status

        settlement = (
            db.query(models.PaymentSettlement)
            .filter(models.PaymentSettlement.payment_id == payment.id)
            .with_for_update()
            .first()
        )
        if settlement and settlement.status == "approved":
            settlement.provider_recovery_amount = (
                refund_request.refund_amount * settlement.provider_share_amount / payment.amount
            ).quantize(Decimal("0.01"))
            settlement.recovery_status = "pending"
    return movement


def ensure_refund_can_restore_previous_booking_status(
    refund_request: models.RefundRequest,
):
    if refund_request.previous_booking_status not in REFUND_RESTORABLE_BOOKING_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Refund request has an invalid previous booking status",
        )


def add_refund_request_status_history(
    refund_request: models.RefundRequest,
    old_status: str,
    new_status: str,
    note: str | None,
    current_user: models.User,
    db: Session,
):
    history = models.RefundRequestStatusHistory(
        refund_request_id=refund_request.id,
        changed_by_user_id=current_user.id,
        old_status=old_status,
        new_status=new_status,
        note=note,
        changed_at=utc_now(),
    )

    db.add(history)


def format_refund_request_response(
    refund_request: models.RefundRequest,
    db: Session,
):
    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == refund_request.booking_id)
        .first()
    )
    payment = (
        db.query(models.Payment)
        .filter(models.Payment.id == refund_request.payment_id)
        .first()
    )

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
        "external_refund_id": refund_request.external_refund_id,
        "failure_code": refund_request.failure_code,
        "failure_message": refund_request.failure_message,
        "booking": format_booking_detail_response(booking, db) if booking else None,
        "payment": format_payment_response(payment, db) if payment else None,
    }
