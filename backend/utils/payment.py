from sqlalchemy.orm import Session

from backend import models
from backend.core.clock import utc_now
from backend.schemas import PaymentStatus
from backend.utils.booking import format_booking_detail_response
from backend.utils.marketplace import format_payment_settlement


def fail_pending_payments_for_booking(booking: models.Booking, db: Session):
    pending_payments = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.status.in_(
                [
                    PaymentStatus.pending,
                    PaymentStatus.checkout_created,
                    PaymentStatus.processing,
                ]
            ),
        )
        .all()
    )

    for payment in pending_payments:
        payment.status = PaymentStatus.failed
        payment.failed_at = utc_now()

    return len(pending_payments)


def format_payment_response(
    payment: models.Payment,
    db: Session,
    *,
    include_settlement: bool = False,
):
    booking = (
        db.query(models.Booking).filter(models.Booking.id == payment.booking_id).first()
    )
    return {
        "id": payment.id,
        "booking_id": payment.booking_id,
        "customer_id": payment.customer_id,
        "provider_profile_id": payment.provider_profile_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status,
        "payment_stage": payment.payment_stage,
        "payment_method": payment.payment_method,
        "idempotency_key": payment.idempotency_key,
        "processing_started_at": payment.processing_started_at,
        "checkout_expires_at": payment.checkout_expires_at,
        "external_payment_id": payment.external_payment_id,
        "conversation_id": payment.conversation_id,
        "basket_id": payment.basket_id,
        "iyzico_token": payment.iyzico_token,
        "checkout_url": payment.checkout_url,
        "iyzico_payment_id": payment.iyzico_payment_id,
        "payment_transaction_id": payment.payment_transaction_id,
        "external_status": payment.external_status,
        "failure_code": payment.failure_code,
        "failure_message": payment.failure_message,
        "created_at": payment.created_at,
        "paid_at": payment.paid_at,
        "authorized_at": payment.authorized_at,
        "voided_at": payment.voided_at,
        "capture_failed_at": payment.capture_failed_at,
        "refunded_at": payment.refunded_at,
        "failed_at": payment.failed_at,
        # Commission and provider payout metadata is an internal/provider
        # concern. Customer responses expose the payment total and status but
        # do not expose the platform split.
        "settlement": (
            format_payment_settlement(
                db.query(models.PaymentSettlement)
                .filter(models.PaymentSettlement.payment_id == payment.id)
                .first()
            )
            if include_settlement
            else None
        ),
        "booking": format_booking_detail_response(booking, db) if booking else None,
    }
