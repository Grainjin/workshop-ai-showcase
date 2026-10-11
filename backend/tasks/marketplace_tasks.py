"""Background tasks for Marketplace settlement approval."""

import asyncio
from datetime import timedelta

from backend import config, models
from backend.core.clock import utc_now
from backend.database import SessionLocal
from backend.schemas import PaymentStatus, SettlementStatus
from backend.services import iyzico as iyzico_service
from backend.tasks.celery_app import celery_app
from backend.utils.marketplace import approve_demo_settlement, format_payment_settlement


APPROVAL_REQUEST_TTL = timedelta(minutes=15)


def _approve_payment_settlement(payment_id: int) -> dict:
    db = SessionLocal()
    try:
        settlement = (
            db.query(models.PaymentSettlement)
            .filter(models.PaymentSettlement.payment_id == payment_id)
            .with_for_update()
            .first()
        )
        if not settlement:
            return {"status": "missing", "payment_id": payment_id}
        if settlement.status == SettlementStatus.approved.value:
            return {"status": "approved", "payment_id": payment_id}
        if settlement.status == SettlementStatus.approve_requested.value:
            requested_at = settlement.approve_requested_at
            if requested_at and requested_at > utc_now() - APPROVAL_REQUEST_TTL:
                return {"status": "already_requested", "payment_id": payment_id}

        payment = db.get(models.Payment, payment_id)
        if not payment or payment.status != PaymentStatus.paid:
            settlement.status = SettlementStatus.approval_failed.value
            settlement.failure_code = "payment_not_paid"
            settlement.failure_message = "Only paid payments can be approved"
            db.commit()
            return {"status": "failed", "payment_id": payment_id}
        if payment.payment_method == "demo":
            approve_demo_settlement(payment, settlement)
            db.commit()
            return {"status": "approved", "payment_id": payment_id,
                    "settlement": format_payment_settlement(settlement)}
        if config.PAYMENT_MODE == "demo" or config.DEMO_MODE:
            return {"status": "disabled", "payment_id": payment_id}
        if not settlement.payment_transaction_id:
            settlement.status = SettlementStatus.approval_failed.value
            settlement.failure_code = "payment_transaction_missing"
            settlement.failure_message = "iyzico payment transaction ID is missing"
            db.commit()
            return {"status": "failed", "payment_id": payment_id}

        settlement.status = SettlementStatus.approve_requested.value
        settlement.approve_requested_at = utc_now()
        settlement.retry_count += 1
        settlement.failure_code = None
        settlement.failure_message = None
        db.commit()
        transaction_id = settlement.payment_transaction_id

        try:
            result = asyncio.run(
                iyzico_service.get_iyzico_client().approve_item(transaction_id)
            )
        except iyzico_service.IyzicoClientError as exc:
            response_data = exc.response_data or {}
            settlement.status = SettlementStatus.approval_failed.value
            settlement.failure_code = str(
                response_data.get("errorCode") or "approve_failed"
            )
            settlement.failure_message = str(
                response_data.get("errorMessage") or str(exc)
            )
            db.commit()
            return {"status": "failed", "payment_id": payment_id}

        if str(result.get("status", "")).lower() != "success":
            settlement.status = SettlementStatus.approval_failed.value
            settlement.failure_code = str(result.get("errorCode") or "approve_failed")
            settlement.failure_message = str(
                result.get("errorMessage") or "iyzico rejected the approval"
            )
            db.commit()
            return {"status": "failed", "payment_id": payment_id}

        settlement.status = SettlementStatus.approved.value
        settlement.approved_at = utc_now()
        db.commit()
        return {
            "status": "approved",
            "payment_id": payment_id,
            "settlement": format_payment_settlement(settlement),
        }
    finally:
        db.close()


@celery_app.task(
    name="marketplace.approve_payment_settlement",
    bind=True,
    max_retries=3,
)
def approve_payment_settlement(self, payment_id: int):
    result = _approve_payment_settlement(payment_id)
    if result.get("status") == "failed":
        raise self.retry(
            countdown=2 ** (self.request.retries + 1),
            exc=RuntimeError("iyzico settlement approval failed"),
        )
    return result


def enqueue_payment_settlement(payment_id: int) -> bool:
    try:
        approve_payment_settlement.delay(payment_id)
        return True
    except Exception:
        return False
