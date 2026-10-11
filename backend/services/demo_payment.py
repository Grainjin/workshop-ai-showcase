"""Local payment simulation. No checkout, card data, or vendor client is involved."""

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import models


@dataclass(frozen=True)
class DemoPaymentResult:
    payment_id: int
    external_status: str = "simulated"


@dataclass(frozen=True)
class DemoRefundResult:
    refund_id: str
    external_status: str = "simulated"


def has_external_payment_evidence(payment: models.Payment) -> bool:
    return any((payment.external_payment_id, payment.iyzico_payment_id,
                payment.payment_transaction_id, payment.iyzico_token, payment.checkout_url))


def is_demo_definitive_failure(payment: models.Payment) -> bool:
    return (payment.payment_method == "demo" and payment.status == "failed"
            and payment.external_status == "simulated"
            and not has_external_payment_evidence(payment))


def complete_demo_payment(
    payment: models.Payment, booking: models.Booking, db: Session,
) -> DemoPaymentResult:
    """Prepare local success; the caller applies the shared paid transition and commit."""
    if payment.booking_id != booking.id or has_external_payment_evidence(payment):
        raise HTTPException(status_code=409, detail="Payment cannot be simulated")
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending payments can be simulated")
    payment.payment_method = "demo"
    payment.external_status = "simulated"
    return DemoPaymentResult(payment_id=payment.id)


def complete_demo_refund(
    payment: models.Payment, amount: Decimal, db: Session,
) -> DemoRefundResult:
    """Confirm a local refund for the shared refund/booking finalizer."""
    if payment.payment_method != "demo" or payment.status != "paid":
        raise HTTPException(status_code=409, detail="Demo payment cannot be refunded in its current state")
    if not amount.is_finite() or amount <= 0 or amount > payment.amount:
        raise HTTPException(status_code=400, detail="Invalid demo refund amount")
    successful = db.query(models.RefundRequest).filter_by(
        payment_id=payment.id, status="approved",
    ).first()
    if successful or payment.refunded_at:
        raise HTTPException(status_code=409, detail="This payment already has a successful refund")
    return DemoRefundResult(refund_id=f"demo-refund-{payment.id}")
