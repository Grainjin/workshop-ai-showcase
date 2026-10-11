"""Payment-provider callbacks.

Customer-authenticated payment initiation remains in the customer bookings
router. This router only exposes the provider callback needed to finalize the
Checkout Form result.
"""

from urllib.parse import urlencode

from fastapi import Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_db
from backend.config import IYZICO_FRONTEND_RETURN_URL
from backend.services import iyzico as iyzico_service
from backend.utils.customer_booking_actions import apply_iyzico_checkout_result
from backend.utils.payment import format_payment_response
from backend.utils.booking import format_booking_detail_response
from backend.utils.response import success_response
from backend.utils.router import ApiRouter


router = ApiRouter(tags=["Payment"])


def _frontend_result_redirect(payment: models.Payment):
    frontend_return_url = payment.frontend_return_url or IYZICO_FRONTEND_RETURN_URL
    if not frontend_return_url:
        return None

    query = urlencode(
        {
            "booking_id": payment.booking_id,
            "payment_status": payment.status,
        }
    )
    separator = "&" if "?" in frontend_return_url else "?"
    return RedirectResponse(
        url=f"{frontend_return_url}{separator}{query}",
        status_code=303,
    )


@router.post("/payments/iyzico/callback")
async def iyzico_checkout_callback(
    token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Retrieve and apply an iyzico Checkout Form result.

    iyzico posts the checkout token to the configured callback URL. The token is
    then used server-to-server to retrieve the authoritative payment result.
    """

    from backend import config
    if config.PAYMENT_MODE == "demo" or config.DEMO_MODE:
        raise HTTPException(status_code=403, detail="External payment callbacks are disabled in demo mode")

    payment = (
        db.query(models.Payment)
        .filter(models.Payment.iyzico_token == token)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment checkout token not found")

    if payment.status in [
        "authorized",
        "paid",
        "voided",
        "refunded",
        "partially_refunded",
    ]:
        redirect = _frontend_result_redirect(payment)
        if redirect:
            return redirect
        return success_response(
            {
                "message": "Payment result was already finalized",
                "payment": format_payment_response(payment, db),
                "booking": format_booking_detail_response(
                    db.get(models.Booking, payment.booking_id), db
                ),
            }
        )

    try:
        result = await iyzico_service.get_iyzico_client().retrieve_checkout_form(
            token=token,
            conversation_id=payment.conversation_id,
        )
    except iyzico_service.IyzicoClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    result_data = await apply_iyzico_checkout_result(payment, result, db)
    redirect = _frontend_result_redirect(payment)
    if redirect:
        return redirect
    return success_response(result_data)
