"""Customer booking actions.

Core booking flow: create, cancel, pay, refund, acceptance, pre-review state changes.
Shared by HTTP APIs and AI confirmations for consistent state rules.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend import config, models
from backend.services import demo_payment
from backend.schemas import (
    BookingCreate,
    BookingStatus,
    NotificationRelatedType,
    NotificationType,
    PaymentStatus,
    RefundAppealCreate,
    RefundRequestStatus,
)
from backend.utils.availability import ensure_provider_available_for_datetime_range
from backend.utils.booking import (
    add_booking_status_history,
    ensure_booking_status,
    format_booking_detail_response,
    get_active_refund_request,
    save_booking,
)
from backend.utils.chat import (
    create_booking_chat_message,
    create_booking_status_chat_message,
    format_chat_message_response,
    format_chat_room_response_with_unread,
    get_or_create_chat_room,
    push_chat_message_to_room_members,
)
from backend.utils.notification import create_admin_notifications, create_notification
from backend.utils.payment import fail_pending_payments_for_booking
from backend.utils.payment import format_payment_response
from backend.utils.marketplace import (
    calculate_commission,
    ensure_payment_settlement,
    format_payment_settlement,
    get_provider_submerchant,
)
from backend.utils.provider_eligibility import require_provider_can_accept_orders
from backend.utils.refund import (
    add_refund_request_status_history,
    format_refund_request_response,
)
from backend.utils.upload import (
    delete_local_upload,
    save_booking_attachment_upload,
    validate_booking_attachments,
)
from backend.core.clock import parse_dt, to_workshop_datetime, utc_now
from backend.config import IYZICO_CALLBACK_URL, IYZICO_CHECKOUT_TTL_SECONDS
from backend.services import iyzico as iyzico_service


async def create_customer_booking_action(
    booking_data: BookingCreate,
    current_user: models.User,
    db: Session,
    attachments: list[UploadFile] | None = None,
):
    """Create a booking request.

    Validates provider and schedule, creates/reuses chat room, saves attachments,
    writes status history, notifies provider, and posts booking message to chat.
    """

    if current_user.role != "customer":
        raise HTTPException(
            status_code=403, detail="Only customers can create bookings"
        )

    validate_booking_attachments(attachments)
    scheduled_start_time = to_workshop_datetime(booking_data.scheduled_start_time)
    scheduled_end_time = to_workshop_datetime(booking_data.scheduled_end_time)

    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking_data.provider_profile_id)
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    require_provider_can_accept_orders(provider_profile, db)

    enabled_service = (
        db.query(models.ProviderApprovedService)
        .filter(
            models.ProviderApprovedService.provider_profile_id == provider_profile.id,
            models.ProviderApprovedService.service_category
            == booking_data.service_category,
            models.ProviderApprovedService.is_enabled.is_(True),
        )
        .first()
    )
    if enabled_service is None:
        raise HTTPException(
            status_code=422,
            detail="Selected service is not enabled for this provider",
        )

    ensure_provider_available_for_datetime_range(
        provider_profile.id,
        scheduled_start_time,
        scheduled_end_time,
        db,
    )

    chat_room = None
    if booking_data.chat_room_id is not None:
        chat_room = (
            db.query(models.ChatRoom)
            .filter(models.ChatRoom.id == booking_data.chat_room_id)
            .first()
        )
        if not chat_room:
            raise HTTPException(status_code=404, detail="Chat room not found")
        if chat_room.customer_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can only create bookings from your own chats",
            )
        if chat_room.provider_profile_id != booking_data.provider_profile_id:
            raise HTTPException(
                status_code=400,
                detail="Chat room provider does not match booking provider",
            )
    else:
        # Booking without prior chat auto-creates a room for follow-up.
        chat_room = get_or_create_chat_room(
            current_user.id, booking_data.provider_profile_id, db
        )

    saved_file_urls = []
    try:
        booking = models.Booking(
            customer_id=current_user.id,
            provider_profile_id=booking_data.provider_profile_id,
            chat_room_id=chat_room.id,
            title=booking_data.title,
            service_category=booking_data.service_category,
            service_description=booking_data.service_description,
            service_address=booking_data.service_address,
            service_latitude=booking_data.service_latitude,
            service_longitude=booking_data.service_longitude,
            customer_current_address=booking_data.customer_current_address,
            customer_current_latitude=booking_data.customer_current_latitude,
            customer_current_longitude=booking_data.customer_current_longitude,
            booking_at=utc_now(),
            scheduled_start_time=scheduled_start_time,
            scheduled_end_time=scheduled_end_time,
            completed_at=None,
            total_amount=Decimal("0.00"),
            quote_amount=None,
            quote_message=None,
            quoted_at=None,
            status=BookingStatus.pending,
            status_note=None,
        )
        db.add(booking)
        db.flush()
        attachment_records = []
        for file in attachments or []:
            if not file.filename:
                continue
            upload_result = await save_booking_attachment_upload(booking.id, file)
            saved_file_urls.append(upload_result["file_url"])
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
            db.flush()
            attachment_records.append(attachment)

        booking_chat_message = create_booking_chat_message(
            chat_room, booking, current_user.id, db, attachment_records
        )
        add_booking_status_history(
            booking,
            "created",
            booking.status,
            "Customer created booking request",
            current_user,
            db,
        )
        notification_message = "You received a new booking request"
        if attachment_records:
            notification_message = (
                f"{notification_message} with {len(attachment_records)} attachment(s)"
            )
        create_notification(
            provider_profile.user_id,
            "New booking request",
            notification_message,
            NotificationType.booking_created,
            NotificationRelatedType.booking,
            booking.id,
            db,
        )
        db.commit()
    except Exception:
        # On DB failure, delete local uploads to avoid orphan files.
        db.rollback()
        for file_url in saved_file_urls:
            delete_local_upload(file_url)
        raise

    db.refresh(booking)
    db.refresh(chat_room)
    db.refresh(booking_chat_message)
    await push_chat_message_to_room_members(booking_chat_message, db)

    return {
        "message": "Booking created successfully",
        "booking": format_booking_detail_response(booking, db),
        "chat_room": format_chat_room_response_with_unread(chat_room, db, current_user),
        "chat_message": format_chat_message_response(booking_chat_message, db),
    }


async def cancel_customer_booking_action(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    """Customer cancels booking.

    Allowed before authorization; completed bookings use the refund flow.
    """

    if current_user.role != "customer":
        raise HTTPException(
            status_code=403, detail="Only customers can cancel bookings"
        )

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.customer_id == current_user.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking,
        [
            BookingStatus.pending,
            BookingStatus.quoted,
            BookingStatus.awaiting_payment,
            BookingStatus.awaiting_visit_payment,
        ],
        "Only pending, quoted, awaiting payment or unpaid visit-fee bookings can be cancelled",
    )
    authorized_payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.customer_id == current_user.id,
            models.Payment.status.in_([
                PaymentStatus.authorized,
                PaymentStatus.capture_failed,
            ]),
        )
        .with_for_update()
        .order_by(models.Payment.created_at.desc(), models.Payment.id.desc())
        .first()
    )
    if authorized_payment:
        if not authorized_payment.iyzico_payment_id or not authorized_payment.conversation_id:
            raise HTTPException(
                status_code=409,
                detail="Authorized payment cannot be released because its iyzico reference is missing",
            )
        try:
            result = await iyzico_service.get_iyzico_client().cancel_payment(
                authorized_payment.iyzico_payment_id,
                authorized_payment.conversation_id,
            )
        except iyzico_service.IyzicoClientError as exc:
            authorized_payment.external_status = "void_failed"
            authorized_payment.failure_code = "void_failed"
            authorized_payment.failure_message = str(exc)
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if str(result.get("status", "")).lower() != "success":
            authorized_payment.external_status = "void_failed"
            authorized_payment.failure_code = str(result.get("errorCode") or "void_failed")
            authorized_payment.failure_message = str(
                result.get("errorMessage") or "iyzico rejected the authorization release"
            )
            db.commit()
            raise HTTPException(status_code=502, detail=authorized_payment.failure_message)
        authorized_payment.status = PaymentStatus.voided
        authorized_payment.voided_at = utc_now()
        authorized_payment.external_status = "voided"
        authorized_payment.failure_code = None
        authorized_payment.failure_message = None
    old_status = booking.status
    booking.status = BookingStatus.cancelled
    booking.status_note = "Customer cancelled booking"
    failed_payment_count = fail_pending_payments_for_booking(booking, db)
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer cancelled the booking",
        booking.status_note,
        db,
        {
            "reason": booking.status_note,
            "failed_pending_payment_count": failed_payment_count,
        },
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Booking cancelled",
            "A customer cancelled a booking",
            NotificationType.booking_cancelled,
            NotificationRelatedType.booking,
            booking.id,
            db,
        )

    result = save_booking(booking, db)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    result["booking"] = format_booking_detail_response(booking, db)
    result["failed_pending_payment_count"] = failed_payment_count
    result["message"] = "Booking cancelled successfully"

    return result


async def create_customer_refund_request_action(
    booking_id: int,
    reason: str,
    current_user: models.User,
    db: Session,
    refund_amount: float | None = None,
):
    if current_user.role != "customer":
        raise HTTPException(
            status_code=403, detail="Only customers can request refunds"
        )

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.customer_id == current_user.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    successful_refund = (
        db.query(models.RefundRequest)
        .filter(
            models.RefundRequest.booking_id == booking.id,
            models.RefundRequest.customer_id == current_user.id,
            models.RefundRequest.status == RefundRequestStatus.approved,
        )
        .first()
    )
    if successful_refund:
        raise HTTPException(
            status_code=400,
            detail="This payment already has a successful refund",
        )

    ensure_booking_status(
        booking,
        [
            BookingStatus.provider_arrived,
            BookingStatus.awaiting_final_quote,
            BookingStatus.final_quote_sent,
            BookingStatus.awaiting_service_payment,
            BookingStatus.service_paid,
            BookingStatus.awaiting_confirmation,
            BookingStatus.completed,
        ],
        "Refunds are available after the provider starts the visit",
    )

    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.customer_id == current_user.id,
            models.Payment.status == PaymentStatus.paid,
        )
        .order_by(models.Payment.created_at.desc())
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=400, detail="Paid payment not found for this booking"
        )

    active_refund_request = (
        db.query(models.RefundRequest)
        .filter(
            models.RefundRequest.payment_id == payment.id,
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
    if active_refund_request:
        raise HTTPException(
            status_code=400, detail="This payment already has a refund request"
        )

    requested_amount = Decimal(str(refund_amount)) if refund_amount is not None else payment.amount
    requested_amount = requested_amount.quantize(Decimal("0.01"))
    if requested_amount <= 0 or requested_amount > payment.amount:
        raise HTTPException(
            status_code=400,
            detail="Refund amount must be greater than zero and no more than the paid amount",
        )

    previous_status = booking.status
    refund_request = models.RefundRequest(
        booking_id=booking.id,
        payment_id=payment.id,
        customer_id=current_user.id,
        provider_profile_id=booking.provider_profile_id,
        reason=reason,
        status=RefundRequestStatus.pending,
        provider_note=None,
        appeal_reason=None,
        admin_note=None,
        previous_booking_status=previous_status,
        created_at=utc_now(),
        responded_at=None,
        appealed_at=None,
        admin_responded_at=None,
        cancelled_at=None,
        refunded_at=None,
        refund_amount=requested_amount,
        external_refund_id=None,
        failure_code=None,
        failure_message=None,
    )
    old_status = booking.status
    booking.status = BookingStatus.refunding
    booking.status_note = reason
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    db.add(refund_request)
    db.flush()
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer requested a refund",
        booking.status_note,
        db,
        {
            "refund_request_id": refund_request.id,
            "refund_status": refund_request.status,
            "reason": refund_request.reason,
            "previous_booking_status": refund_request.previous_booking_status,
            "payment_id": payment.id,
        },
    )
    add_refund_request_status_history(
        refund_request,
        "created",
        refund_request.status,
        refund_request.reason,
        current_user,
        db,
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Refund requested",
            "A customer requested a refund",
            NotificationType.refund_requested,
            NotificationRelatedType.refund_request,
            refund_request.id,
            db,
        )

    db.commit()
    db.refresh(refund_request)
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)

    return {
        "message": "Refund request created successfully",
        "refund_request": format_refund_request_response(refund_request, db),
        "booking": format_booking_detail_response(booking, db),
    }


async def appeal_customer_refund_request_action(
    refund_request_id: int,
    appeal_data: RefundAppealCreate,
    current_user: models.User,
    db: Session,
):
    """Customer appeals to admin after provider rejects refund."""

    if current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Only customers can appeal refunds")

    refund_request = (
        db.query(models.RefundRequest)
        .filter(
            models.RefundRequest.id == refund_request_id,
            models.RefundRequest.customer_id == current_user.id,
        )
        .first()
    )
    if not refund_request:
        raise HTTPException(status_code=404, detail="Refund request not found")
    if refund_request.status != RefundRequestStatus.rejected:
        raise HTTPException(
            status_code=400,
            detail="Only provider rejected refund requests can be appealed",
        )

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == refund_request.booking_id,
            models.Booking.customer_id == current_user.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking,
        [BookingStatus.refunding],
        "Only refunding bookings can be appealed",
    )
    old_refund_status = refund_request.status
    refund_request.status = RefundRequestStatus.appealed
    refund_request.appeal_reason = appeal_data.appeal_reason
    refund_request.appealed_at = utc_now()
    booking.status_note = appeal_data.appeal_reason
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        booking.status,
        current_user.id,
        "Customer appealed the rejected refund request",
        booking.status_note,
        db,
        {
            "refund_request_id": refund_request.id,
            "refund_status": refund_request.status,
            "appeal_reason": refund_request.appeal_reason,
            "appealed_at": refund_request.appealed_at,
        },
    )
    add_refund_request_status_history(
        refund_request,
        old_refund_status,
        refund_request.status,
        refund_request.appeal_reason,
        current_user,
        db,
    )
    create_admin_notifications(
        "Refund appeal submitted",
        "A customer appealed a rejected refund request",
        NotificationType.refund_appealed,
        NotificationRelatedType.refund_request,
        refund_request.id,
        db,
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == refund_request.provider_profile_id)
        .first()
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Refund appeal submitted",
            "The customer appealed your refund decision to customer service",
            NotificationType.refund_appealed,
            NotificationRelatedType.refund_request,
            refund_request.id,
            db,
        )
    db.commit()
    db.refresh(refund_request)
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)

    return {
        "message": "Refund request appealed successfully",
        "refund_request": format_refund_request_response(refund_request, db),
        "booking": format_booking_detail_response(booking, db),
    }


def _checkout_buyer_details(
    booking: models.Booking,
    current_user: models.User,
    db: Session,
) -> tuple[dict, dict]:
    customer_profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )
    name_parts = (current_user.name or "Workshop Customer").split(maxsplit=1)
    first_name = current_user.first_name or name_parts[0]
    last_name = current_user.last_name or (name_parts[1] if len(name_parts) > 1 else "Customer")
    city = (
        customer_profile.service_province
        if customer_profile and customer_profile.service_province
        else "Istanbul"
    )
    phone = (
        customer_profile.phone_number
        if customer_profile and customer_profile.phone_number
        else "+905000000000"
    )
    registration_date = (current_user.created_at or utc_now()).strftime("%Y-%m-%d %H:%M:%S")
    last_login_date = (current_user.last_login_at or current_user.created_at or utc_now()).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    buyer = {
        "id": str(current_user.id),
        "name": first_name,
        "surname": last_name,
        "identityNumber": str(current_user.id).zfill(11),
        "email": current_user.email,
        "gsmNumber": phone,
        "registrationDate": registration_date,
        "lastLoginDate": last_login_date,
        "registrationAddress": booking.service_address,
        "city": city,
        "country": "Turkey",
        "ip": "127.0.0.1",
    }
    address = {
        "address": booking.service_address,
        "contactName": current_user.name or f"{first_name} {last_name}",
        "city": city,
        "country": "Turkey",
    }
    return buyer, address


def _build_checkout_payload(
    booking: models.Booking,
    payment: models.Payment,
    current_user: models.User,
    db: Session,
) -> dict:
    buyer, address = _checkout_buyer_details(booking, current_user, db)
    submerchant = get_provider_submerchant(booking.provider_profile_id, db)
    if not submerchant or submerchant.status != "active" or not submerchant.submerchant_key:
        raise HTTPException(status_code=409, detail="Provider payout account is not ready")
    amount = float(payment.amount)
    _, provider_amount = calculate_commission(Decimal(str(payment.amount)))
    return {
        "locale": "en",
        "conversationId": payment.conversation_id,
        "price": amount,
        "paidPrice": amount,
        "currency": payment.currency,
        "basketId": payment.basket_id,
        "paymentGroup": "PRODUCT",
        "callbackUrl": IYZICO_CALLBACK_URL,
        "buyer": buyer,
        "shippingAddress": address,
        "billingAddress": address,
        "basketItems": [
            {
                "id": str(booking.id),
                "price": amount,
                "name": booking.title,
                "category1": "Service",
                "itemType": "VIRTUAL",
                "subMerchantKey": submerchant.submerchant_key,
                "subMerchantPrice": float(provider_amount),
            }
        ],
    }


def _external_amount_matches(payment: models.Payment, result: dict) -> bool:
    raw_amount = result.get("paidPrice", result.get("price"))
    if raw_amount is None:
        return False
    try:
        return Decimal(str(raw_amount)).quantize(Decimal("0.01")) == Decimal(
            str(payment.amount)
        ).quantize(Decimal("0.01"))
    except Exception:
        return False


async def apply_iyzico_checkout_result(
    payment: models.Payment,
    result: dict,
    db: Session,
):
    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == payment.booking_id)
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if payment.status in [
        PaymentStatus.authorized,
        PaymentStatus.paid,
        PaymentStatus.voided,
        PaymentStatus.refunded,
        PaymentStatus.partially_refunded,
    ]:
        return {
            "message": "Payment result was already finalized",
            "payment": format_payment_response(payment, db),
            "booking": format_booking_detail_response(booking, db),
        }

    earlier_uncertainty = _requires_payment_reconciliation(payment, utc_now())
    external_status = str(result.get("paymentStatus") or result.get("status") or "").lower()
    # A later rejection cannot prove that an earlier uncertain response was uncharged.
    payment.external_status = (
        "reconciliation_required"
        if earlier_uncertainty and external_status in {"failure", "failed"}
        else external_status or None
    )
    iyzico_payment_id = result.get("paymentId")
    if iyzico_payment_id:
        payment.iyzico_payment_id = str(iyzico_payment_id)
        payment.external_payment_id = str(iyzico_payment_id)

    transactions = result.get("itemTransactions") or []
    transaction = transactions[0] if transactions and isinstance(transactions[0], dict) else None
    transaction_id = result.get("paymentTransactionId") or (
        transaction.get("paymentTransactionId") if transaction else None
    )
    if transaction_id:
        payment.payment_transaction_id = str(transaction_id)

    fraud_status = result.get("fraudStatus")
    if external_status != "success" or fraud_status == -1:
        payment.status = PaymentStatus.failed
        payment.processing_started_at = None
        payment.checkout_expires_at = None
        payment.failed_at = utc_now()
        payment.failure_code = str(result.get("errorCode") or "payment_failed")
        payment.failure_message = str(result.get("errorMessage") or "iyzico payment failed")
        db.commit()
        db.refresh(payment)
        db.refresh(booking)
        return {
            "message": "Payment failed",
            "payment": format_payment_response(payment, db),
            "booking": format_booking_detail_response(booking, db),
        }

    if fraud_status == 0:
        payment.status = PaymentStatus.processing
        payment.processing_started_at = None
        payment.checkout_expires_at = None
        db.commit()
        db.refresh(payment)
        db.refresh(booking)
        return {
            "message": "Payment is pending iyzico review",
            "payment": format_payment_response(payment, db),
            "booking": format_booking_detail_response(booking, db),
        }

    if not _external_amount_matches(payment, result):
        payment.status = PaymentStatus.failed
        payment.processing_started_at = None
        payment.checkout_expires_at = None
        payment.failed_at = utc_now()
        payment.failure_code = "payment_amount_mismatch"
        payment.failure_message = "iyzico amount does not match the local payment amount"
        db.commit()
        raise HTTPException(status_code=400, detail=payment.failure_message)

    result_currency = str(result.get("currency") or payment.currency).upper()
    if result_currency != payment.currency.upper():
        payment.status = PaymentStatus.failed
        payment.processing_started_at = None
        payment.checkout_expires_at = None
        payment.failed_at = utc_now()
        payment.failure_code = "payment_currency_mismatch"
        payment.failure_message = "iyzico currency does not match the local payment currency"
        db.commit()
        raise HTTPException(status_code=400, detail=payment.failure_message)

    phase = str(result.get("phase") or result.get("paymentPhase") or "").upper()
    if phase in {"PRE_AUTH", "PREAUTH"}:
        payment.status = PaymentStatus.failed
        payment.failure_code = "unexpected_payment_phase"
        payment.failure_message = "The direct-payment checkout returned an authorization result"
        payment.failed_at = utc_now()
        db.commit()
        raise HTTPException(status_code=400, detail=payment.failure_message)

    payment.payment_method = "iyzico_checkout"
    return await _finalize_paid_payment(payment, booking, db, transaction=transaction)


async def _finalize_paid_payment(
    payment: models.Payment, booking: models.Booking, db: Session,
    *, transaction: dict | None = None,
):
    """Shared successful-payment transition, chat, notification and settlement."""
    now = utc_now()
    payment.status = PaymentStatus.paid
    payment.processing_started_at = None
    payment.checkout_expires_at = None
    payment.authorized_at = None
    payment.paid_at = now
    payment.failed_at = None
    payment.failure_code = None
    payment.failure_message = None
    booking_status_chat_message = None
    expected_status = (
        BookingStatus.visit_paid
        if payment.payment_stage == "visit_fee"
        else BookingStatus.service_paid
    )
    expected_previous = (
        {BookingStatus.awaiting_visit_payment, BookingStatus.awaiting_payment}
        if payment.payment_stage == "visit_fee"
        else {BookingStatus.awaiting_service_payment}
    )
    if booking.status in expected_previous:
        old_status = booking.status
        booking.status = expected_status
        booking.status_note = (
            "Visit fee paid; provider must submit arrival evidence"
            if payment.payment_stage == "visit_fee"
            else "Service fee paid; provider can complete the service"
        )
        add_booking_status_history(
            booking,
            old_status,
            booking.status,
            booking.status_note,
            db.get(models.User, payment.customer_id),
            db,
        )
        booking_status_chat_message = create_booking_status_chat_message(
            booking,
            old_status,
            payment.customer_id,
            (
                "Customer paid the visit fee; provider can start the visit"
                if payment.payment_stage == "visit_fee"
                else "Customer paid the final service quote"
            ),
            booking.status_note,
            db,
            {
                "payment_id": payment.id,
                "payment_status": payment.status,
                "amount": payment.amount,
                "currency": payment.currency,
                "paid_at": payment.paid_at,
            },
        )
        provider_profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.id == booking.provider_profile_id)
            .first()
        )
        if provider_profile:
            create_notification(
                provider_profile.user_id,
                "Payment received",
                ("Demo payment — no real charge." if payment.payment_method == "demo"
                 else "A customer paid a booking payment through iyzico Sandbox"),
                NotificationType.payment_paid,
                NotificationRelatedType.payment,
                payment.id,
                db,
            )
    settlement = ensure_payment_settlement(payment, db, transaction=transaction)
    db.commit()
    db.refresh(payment)
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    return {
        "message": "Payment received and booking status updated",
        "payment": format_payment_response(payment, db),
        "booking": format_booking_detail_response(booking, db),
        "settlement": format_payment_settlement(settlement),
    }


def _is_definitively_uncharged_failure(payment: models.Payment) -> bool:
    """Only an explicit rejection without external checkout/payment evidence is retryable."""
    return (
        payment.status == PaymentStatus.failed
        and (payment.external_status or "").strip().lower() in {"failure", "failed"}
        and not any((
            payment.external_payment_id, payment.iyzico_payment_id,
            payment.payment_transaction_id, payment.iyzico_token, payment.checkout_url,
        ))
    )


def _requires_payment_reconciliation(payment: models.Payment, now: datetime) -> bool:
    if payment.status == PaymentStatus.pending:
        return any((
            payment.external_status, payment.external_payment_id, payment.iyzico_payment_id,
            payment.payment_transaction_id, payment.iyzico_token, payment.checkout_url,
        ))
    if payment.status == PaymentStatus.failed:
        return not _is_definitively_uncharged_failure(payment)
    if payment.status == PaymentStatus.checkout_created:
        expires = parse_dt(payment.checkout_expires_at)
        return not expires or expires <= now
    if payment.status == PaymentStatus.processing:
        started = parse_dt(payment.processing_started_at)
        return (
            payment.external_status != "checkout_initializing"
            or not started
            or started <= now - timedelta(seconds=IYZICO_CHECKOUT_TTL_SECONDS)
        )
    return False


def create_replacement_payment_attempt(
    failed_payment: models.Payment,
    amount: Decimal,
    idempotency_key: str,
    now: datetime,
    db: Session,
) -> models.Payment:
    """Create a fresh pending attempt only after a definitive uncharged failure."""
    if not _is_definitively_uncharged_failure(failed_payment):
        raise HTTPException(status_code=409, detail="Payment requires reconciliation before retry")
    replacement = models.Payment(
        booking_id=failed_payment.booking_id,
        customer_id=failed_payment.customer_id,
        provider_profile_id=failed_payment.provider_profile_id,
        amount=amount,
        currency=failed_payment.currency,
        status=PaymentStatus.pending,
        payment_stage=failed_payment.payment_stage,
        payment_method="iyzico_checkout",
        idempotency_key=idempotency_key,
        created_at=now,
    )
    db.add(replacement)
    db.flush()
    return replacement


async def _pay_demo_booking(
    booking: models.Booking, key: str, stage: str, db: Session,
):
    keyed = db.query(models.Payment).filter_by(
        customer_id=booking.customer_id, idempotency_key=key,
    ).first()
    if keyed:
        if keyed.booking_id != booking.id or keyed.payment_stage != stage:
            raise HTTPException(status_code=409, detail="Idempotency-Key belongs to another booking or payment stage")
        if keyed.payment_method != "demo" or demo_payment.has_external_payment_evidence(keyed):
            raise HTTPException(status_code=409, detail="External payment requires reconciliation")
        if keyed.status != PaymentStatus.pending:
            return {
                "message": "Demo payment — no real charge.",
                "payment": format_payment_response(keyed, db),
                "booking": format_booking_detail_response(booking, db),
                "payment_page_url": None,
                "token": None,
            }

    attempts = db.query(models.Payment).filter_by(
        booking_id=booking.id, customer_id=booking.customer_id, payment_stage=stage,
    ).order_by(models.Payment.created_at.desc(), models.Payment.id.desc()).all()
    if not attempts:
        raise HTTPException(status_code=400, detail="Pending payment not found for this booking")
    payment = keyed or attempts[0]
    if any(
        not demo_payment.is_demo_definitive_failure(attempt)
        for attempt in attempts if attempt.id != payment.id
    ):
        raise HTTPException(status_code=409, detail="An existing payment prevents a new demo attempt")
    if payment.status != PaymentStatus.pending and not demo_payment.is_demo_definitive_failure(payment):
        raise HTTPException(status_code=409, detail="Only a simulated definitive failure can be retried")
    if payment.status == PaymentStatus.pending and (
        payment.external_status or demo_payment.has_external_payment_evidence(payment)
        or (payment.idempotency_key and payment.idempotency_key != key)
    ):
        raise HTTPException(status_code=409, detail="An existing payment prevents a new demo attempt")
    allowed = ([BookingStatus.awaiting_visit_payment, BookingStatus.awaiting_payment]
               if stage == "visit_fee" else [BookingStatus.awaiting_service_payment])
    ensure_booking_status(booking, allowed, "This booking is not waiting for this payment")
    if payment.status == PaymentStatus.failed:
        payment = models.Payment(
            booking_id=booking.id, customer_id=booking.customer_id,
            provider_profile_id=booking.provider_profile_id,
            amount=payment.amount, currency=payment.currency, payment_stage=stage,
            status=PaymentStatus.pending, payment_method="demo", created_at=utc_now(),
        )
        db.add(payment)
        db.flush()
    payment.idempotency_key = key
    demo_payment.complete_demo_payment(payment, booking, db)
    result = await _finalize_paid_payment(payment, booking, db)
    result.update(message="Demo payment — no real charge.", payment_page_url=None, token=None)
    return result


async def pay_customer_booking_action(
    booking_id: int,
    payment_method: str,
    current_user: models.User,
    db: Session,
    idempotency_key: str | None = None,
    payment_stage: str = "visit_fee",
    frontend_return_url: str | None = None,
):
    if current_user.role != "customer":
        raise HTTPException(status_code=403, detail="Only customers can pay bookings")

    if not payment_method.strip():
        raise HTTPException(status_code=400, detail="Payment method cannot be empty")
    if payment_stage not in {"visit_fee", "service_fee"}:
        raise HTTPException(status_code=400, detail="Unsupported payment stage")

    normalized_idempotency_key = (idempotency_key or "").strip()
    if not normalized_idempotency_key:
        normalized_idempotency_key = f"legacy-{uuid4().hex}"
    if len(normalized_idempotency_key) > 128:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key must be at most 128 characters",
        )

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.customer_id == current_user.id,
        )
        .with_for_update()
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if config.PAYMENT_MODE == "demo":
        return await _pay_demo_booking(booking, normalized_idempotency_key, payment_stage, db)
    if config.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Public demo requires simulated payments")

    allowed_statuses = (
        [BookingStatus.awaiting_visit_payment, BookingStatus.awaiting_payment]
        if payment_stage == "visit_fee"
        else [BookingStatus.awaiting_service_payment]
    )
    ensure_booking_status(booking, allowed_statuses, "This booking is not waiting for this payment")
    amount = (
        (booking.visit_fee_amount or booking.quote_amount)
        if payment_stage == "visit_fee"
        else booking.final_quote_amount
    )
    if amount is None:
        raise HTTPException(status_code=400, detail="Booking has no amount for this payment stage")

    keyed_payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.customer_id == current_user.id,
            models.Payment.idempotency_key == normalized_idempotency_key,
        )
        .first()
    )
    if keyed_payment and keyed_payment.booking_id != booking.id:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was already used for another booking",
        )

    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.customer_id == current_user.id,
            models.Payment.payment_stage == payment_stage,
            models.Payment.status.in_(
                [
                    PaymentStatus.pending,
                    PaymentStatus.checkout_created,
                    PaymentStatus.processing,
                ]
            ),
        )
        .order_by(models.Payment.created_at.desc(), models.Payment.id.desc())
        .first()
    )

    now = utc_now()
    if keyed_payment and keyed_payment.booking_id == booking.id:
        payment = keyed_payment

    # Preserve same-key replay and all external evidence, including pending review.
    if payment and keyed_payment and _requires_payment_reconciliation(payment, now):
        return {
            "message": "Payment requires reconciliation before retry",
            "payment": format_payment_response(payment, db),
            "booking": format_booking_detail_response(booking, db),
        }
    if not keyed_payment or payment.status == PaymentStatus.pending:
        previous_attempts = db.query(models.Payment).filter(
            models.Payment.booking_id == booking.id,
            models.Payment.customer_id == current_user.id,
            models.Payment.payment_stage == payment_stage,
            models.Payment.status.in_([
                PaymentStatus.pending, PaymentStatus.failed,
                PaymentStatus.checkout_created, PaymentStatus.processing,
                PaymentStatus.authorized, PaymentStatus.paid, PaymentStatus.voided,
                PaymentStatus.refunded, PaymentStatus.partially_refunded,
            ]),
        ).all()
        if any(
            _requires_payment_reconciliation(attempt, now)
            or (
                payment and payment.status == PaymentStatus.pending
                and attempt.id != payment.id
                and attempt.status not in {PaymentStatus.pending, PaymentStatus.failed}
            )
            for attempt in previous_attempts
        ):
            raise HTTPException(status_code=409, detail="Payment requires reconciliation before retry")

    if (
        payment
        and payment.status in [
            PaymentStatus.checkout_created,
            PaymentStatus.processing,
        ]
        and frontend_return_url
        and payment.frontend_return_url != frontend_return_url
    ):
        payment.frontend_return_url = frontend_return_url
        db.commit()
        db.refresh(payment)
        db.refresh(booking)

    if keyed_payment and keyed_payment.booking_id == booking.id:
        if payment.status in [
            PaymentStatus.authorized,
            PaymentStatus.paid,
            PaymentStatus.voided,
            PaymentStatus.refunded,
            PaymentStatus.partially_refunded,
        ]:
            return {
                "message": "Payment result was already finalized",
                "payment": format_payment_response(payment, db),
                "booking": format_booking_detail_response(booking, db),
                "payment_page_url": payment.checkout_url,
                "token": payment.iyzico_token,
            }
        if payment.status == PaymentStatus.failed:
            return {
                "message": "Payment attempt failed. Start a new payment attempt.",
                "payment": format_payment_response(payment, db),
                "booking": format_booking_detail_response(booking, db),
            }

    if not payment and not keyed_payment:
        latest_payment = (
            db.query(models.Payment)
            .filter(
                models.Payment.booking_id == booking.id,
                models.Payment.customer_id == current_user.id,
                models.Payment.payment_stage == payment_stage,
            )
            .order_by(models.Payment.created_at.desc(), models.Payment.id.desc())
            .first()
        )
        if latest_payment and latest_payment.status == PaymentStatus.failed:
            payment = create_replacement_payment_attempt(
                latest_payment, amount, normalized_idempotency_key, now, db
            )

    if not payment:
        raise HTTPException(
            status_code=400,
            detail="Pending payment not found for this booking",
        )

    if payment.status == PaymentStatus.checkout_created:
        return {
            "message": "Payment checkout already created",
            "payment": format_payment_response(payment, db),
            "booking": format_booking_detail_response(booking, db),
            "payment_page_url": payment.checkout_url,
            "token": payment.iyzico_token,
        }

    if payment.status == PaymentStatus.processing:
        return {
            "message": "Payment checkout is being prepared",
            "payment": format_payment_response(payment, db),
            "booking": format_booking_detail_response(booking, db),
            "payment_page_url": payment.checkout_url,
            "token": payment.iyzico_token,
        }

    payment.idempotency_key = payment.idempotency_key or normalized_idempotency_key
    payment.payment_method = "iyzico_checkout"
    if frontend_return_url:
        payment.frontend_return_url = frontend_return_url
    payment.conversation_id = payment.conversation_id or (
        f"booking-{booking.id}-payment-{payment.id}"
    )
    payment.basket_id = payment.basket_id or payment.conversation_id
    payment.status = PaymentStatus.processing
    payment.processing_started_at = now
    payment.checkout_expires_at = None
    payment.external_status = "checkout_initializing"
    payment.failed_at = None
    payment.failure_code = None
    payment.failure_message = None
    db.commit()
    db.refresh(payment)
    db.refresh(booking)
    checkout_payload = _build_checkout_payload(booking, payment, current_user, db)
    try:
        result = await iyzico_service.get_iyzico_client().initialize_checkout_form(
            checkout_payload
        )
    except iyzico_service.IyzicoClientError as exc:
        payment.status = PaymentStatus.failed
        payment.external_status = "checkout_initialize_failed"
        payment.failure_code = "checkout_initialize_failed"
        payment.failure_message = str(exc)
        payment.failed_at = utc_now()
        payment.processing_started_at = None
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Retain provider evidence even if initialization returns an incomplete or failed response.
    payment.external_status = str(result.get("status") or "unknown").lower()
    result_payment_status = str(result.get("paymentStatus") or "").lower()
    if result_payment_status and result_payment_status not in {"failure", "failed"}:
        payment.external_status = result_payment_status
    if result.get("paymentId"):
        payment.iyzico_payment_id = str(result["paymentId"])
        payment.external_payment_id = str(result["paymentId"])
    if result.get("token"):
        payment.iyzico_token = str(result["token"])
    if result.get("paymentPageUrl"):
        payment.checkout_url = str(result["paymentPageUrl"])
    transactions = result.get("itemTransactions") or []
    transaction = transactions[0] if transactions and isinstance(transactions[0], dict) else None
    transaction_id = result.get("paymentTransactionId") or (
        transaction.get("paymentTransactionId") if transaction else None
    )
    if transaction_id:
        payment.payment_transaction_id = str(transaction_id)

    if str(result.get("status", "")).lower() != "success":
        payment.status = PaymentStatus.failed
        payment.failure_code = str(result.get("errorCode") or "checkout_initialize_failed")
        payment.failure_message = str(
            result.get("errorMessage") or "iyzico checkout initialization failed"
        )
        payment.failed_at = utc_now()
        payment.processing_started_at = None
        db.commit()
        raise HTTPException(status_code=502, detail=payment.failure_message)

    token = result.get("token")
    checkout_url = result.get("paymentPageUrl")
    if not token or not checkout_url:
        payment.status = PaymentStatus.failed
        payment.failure_code = "checkout_initialize_failed"
        payment.failure_message = "iyzico checkout response did not include a payment page"
        payment.failed_at = utc_now()
        payment.processing_started_at = None
        db.commit()
        raise HTTPException(
            status_code=502,
            detail="iyzico checkout response did not include a payment page",
        )

    payment.status = PaymentStatus.checkout_created
    payment.processing_started_at = None
    payment.checkout_expires_at = now + timedelta(seconds=IYZICO_CHECKOUT_TTL_SECONDS)
    payment.iyzico_token = str(token)
    payment.checkout_url = str(checkout_url)
    payment.external_status = "checkout_created"
    payment.failed_at = None
    payment.failure_code = None
    payment.failure_message = None
    db.commit()
    db.refresh(payment)
    db.refresh(booking)
    return {
        "message": "iyzico checkout created",
        "payment": format_payment_response(payment, db),
        "booking": format_booking_detail_response(booking, db),
        "payment_page_url": payment.checkout_url,
        "token": payment.iyzico_token,
    }


async def accept_customer_booking_quote_action(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    if current_user.role != "customer":
        raise HTTPException(
            status_code=403, detail="Only customers can accept booking quotes"
        )

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.customer_id == current_user.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking, [BookingStatus.quoted], "Only quoted bookings can be accepted"
    )
    if booking.quote_amount is None:
        raise HTTPException(status_code=400, detail="Booking has no quote amount")

    visit_fee = Decimal(str(booking.visit_fee_amount or booking.quote_amount)).quantize(
        Decimal("0.01")
    )
    existing_payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.payment_stage == "visit_fee",
            models.Payment.status.in_(
                [
                    PaymentStatus.pending,
                    PaymentStatus.checkout_created,
                    PaymentStatus.processing,
                    PaymentStatus.paid,
                ]
            ),
        )
        .first()
    )
    if existing_payment:
        raise HTTPException(
            status_code=400,
            detail="This booking already has a pending or paid payment",
        )

    now = utc_now()
    payment = models.Payment(
        booking_id=booking.id,
        customer_id=current_user.id,
        provider_profile_id=booking.provider_profile_id,
        amount=visit_fee,
        currency="TRY",
        status=PaymentStatus.pending,
        payment_stage="visit_fee",
        payment_method="demo" if config.PAYMENT_MODE == "demo" else "iyzico_checkout",
        external_payment_id=None,
        created_at=now,
        paid_at=None,
        refunded_at=None,
    )
    db.add(payment)
    db.flush()

    old_status = booking.status
    booking.status = BookingStatus.awaiting_visit_payment
    booking.status_note = "Customer accepted the quote and is waiting to pay the visit fee"
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer accepted the quote. Visit-fee payment is pending",
        booking.status_note,
        db,
        {
            "payment_id": payment.id,
            "payment_status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
        },
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Quote accepted",
            "A customer accepted your quote and is waiting to pay",
            NotificationType.booking_quote_accepted,
            NotificationRelatedType.booking,
            booking.id,
            db,
        )

    db.commit()
    db.refresh(payment)
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)

    return {
        "message": "Quote accepted. Payment is pending",
        "payment": format_payment_response(payment, db),
        "booking": format_booking_detail_response(booking, db),
        "chat_message": (
            format_chat_message_response(booking_status_chat_message, db)
            if booking_status_chat_message
            else None
        ),
    }


async def reject_customer_booking_quote_action(
    booking_id: int,
    status_note: str,
    current_user: models.User,
    db: Session,
):
    if current_user.role != "customer":
        raise HTTPException(
            status_code=403, detail="Only customers can reject booking quotes"
        )

    if not status_note.strip():
        raise HTTPException(status_code=400, detail="Status note cannot be empty")

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.customer_id == current_user.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking, [BookingStatus.quoted], "Only quoted bookings can reject a quote"
    )
    old_status = booking.status
    booking.status = BookingStatus.pending
    booking.status_note = status_note.strip()
    latest_revision = (
        db.query(models.BookingQuoteRevision)
        .filter(models.BookingQuoteRevision.booking_id == booking.id)
        .order_by(models.BookingQuoteRevision.revision_number.desc())
        .with_for_update()
        .first()
    )
    if latest_revision:
        latest_revision.declined_at = utc_now()
        latest_revision.decline_reason = status_note.strip()
    booking.quote_amount = None
    booking.quote_message = None
    booking.expected_service_amount = None
    booking.visit_fee_amount = None
    booking.quoted_at = None
    failed_payment_count = fail_pending_payments_for_booking(booking, db)
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer rejected the quote",
        booking.status_note,
        db,
        {
            "reason": booking.status_note,
            "failed_pending_payment_count": failed_payment_count,
        },
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Quote rejected",
            "A customer rejected your quote",
            NotificationType.booking_quote_rejected,
            NotificationRelatedType.booking,
            booking.id,
            db,
        )

    result = save_booking(booking, db)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    result["booking"] = format_booking_detail_response(booking, db)
    result["failed_pending_payment_count"] = failed_payment_count
    result["message"] = "Quote rejected. Provider can submit another quote"

    return result


async def accept_customer_final_quote_action(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == booking_id, models.Booking.customer_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    ensure_booking_status(booking, [BookingStatus.final_quote_sent], "Only a sent final quote can be accepted")
    if booking.final_quote_amount is None:
        raise HTTPException(status_code=400, detail="Booking has no final quote amount")
    existing = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.payment_stage == "service_fee",
            models.Payment.status.in_([PaymentStatus.pending, PaymentStatus.checkout_created, PaymentStatus.paid]),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="The service payment already exists")
    payment = models.Payment(
        booking_id=booking.id,
        customer_id=current_user.id,
        provider_profile_id=booking.provider_profile_id,
        amount=booking.final_quote_amount,
        currency="TRY",
        status=PaymentStatus.pending,
        payment_stage="service_fee",
        payment_method="demo" if config.PAYMENT_MODE == "demo" else "iyzico_checkout",
        created_at=utc_now(),
    )
    db.add(payment)
    db.flush()
    revision = (
        db.query(models.BookingQuoteRevision)
        .filter(models.BookingQuoteRevision.booking_id == booking.id)
        .order_by(models.BookingQuoteRevision.revision_number.desc())
        .first()
    )
    if revision:
        revision.customer_confirmed_at = utc_now()
    old_status = booking.status
    booking.status = BookingStatus.awaiting_service_payment
    booking.final_quote_confirmed_at = utc_now()
    booking.status_note = "Customer accepted the final quote and is waiting to pay"
    add_booking_status_history(booking, old_status, booking.status, booking.status_note, current_user, db)
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer accepted the final quote",
        booking.status_note,
        db,
        {
            "payment_id": payment.id,
            "payment_status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
        },
    )
    db.commit()
    db.refresh(payment)
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    return {
        "message": "Final quote accepted. Service payment is due",
        "payment": format_payment_response(payment, db),
        "booking": format_booking_detail_response(booking, db),
    }


async def reject_customer_final_quote_action(
    booking_id: int,
    status_note: str,
    current_user: models.User,
    db: Session,
):
    if not status_note.strip():
        raise HTTPException(status_code=400, detail="Status note cannot be empty")
    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == booking_id, models.Booking.customer_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    ensure_booking_status(booking, [BookingStatus.final_quote_sent], "Only a sent final quote can be declined")
    old_status = booking.status
    booking.status = BookingStatus.awaiting_final_quote
    declined_at = utc_now()
    booking.final_quote_declined_at = declined_at
    booking.final_quote_decline_reason = status_note.strip()
    booking.status_note = status_note.strip()
    latest_revision = (
        db.query(models.BookingQuoteRevision)
        .filter(models.BookingQuoteRevision.booking_id == booking.id)
        .order_by(models.BookingQuoteRevision.revision_number.desc())
        .with_for_update()
        .first()
    )
    if latest_revision:
        latest_revision.declined_at = declined_at
        latest_revision.decline_reason = status_note.strip()
    add_booking_status_history(booking, old_status, booking.status, booking.status_note, current_user, db)
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer declined the final quote",
        booking.status_note,
        db,
        {
            "reason": booking.status_note,
            "final_quote_amount": booking.final_quote_amount,
            "final_quote_message": booking.final_quote_message,
        },
    )
    db.commit()
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    return {"message": "Final quote declined. Provider can submit a revised quote", "booking": format_booking_detail_response(booking, db)}


async def close_final_quote_negotiation_action(
    booking_id: int,
    status_note: str,
    current_user: models.User,
    db: Session,
):
    if not status_note.strip():
        raise HTTPException(status_code=400, detail="Status note cannot be empty")
    booking = (
        db.query(models.Booking)
        .filter(models.Booking.id == booking_id, models.Booking.customer_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    ensure_booking_status(
        booking,
        [
            BookingStatus.visit_paid,
            BookingStatus.provider_arrived,
            BookingStatus.awaiting_final_quote,
            BookingStatus.final_quote_sent,
            BookingStatus.awaiting_service_payment,
            BookingStatus.service_paid,
            BookingStatus.accepted,
        ],
        "This booking cannot be cancelled at this stage",
    )
    old_status = booking.status
    fail_pending_payments_for_booking(booking, db)
    booking.status = BookingStatus.visit_completed_closed
    booking.closed_reason = "customer_cancelled_without_refund"
    booking.status_note = status_note.strip()
    add_booking_status_history(booking, old_status, booking.status, booking.status_note, current_user, db)
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer cancelled the booking without requesting a refund",
        booking.status_note,
        db,
    )
    db.commit()
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    return {"message": "Booking closed without refund", "booking": format_booking_detail_response(booking, db)}


async def _complete_direct_paid_booking(
    booking: models.Booking,
    payment: models.Payment,
    current_user: models.User,
    db: Session,
):
    now = utc_now()
    revision = (
        db.query(models.BookingQuoteRevision)
        .filter(models.BookingQuoteRevision.booking_id == booking.id)
        .order_by(models.BookingQuoteRevision.revision_number.desc())
        .first()
    )
    if revision:
        revision.used_for_payment_at = revision.used_for_payment_at or payment.paid_at or now
    settlement = ensure_payment_settlement(payment, db)
    old_status = booking.status
    booking.status = BookingStatus.completed
    booking.completed_at = now
    booking.status_note = "Customer confirmed service completion"
    add_booking_status_history(booking, old_status, booking.status, booking.status_note, current_user, db)
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer confirmed service completion",
        booking.status_note,
        db,
        {"completed_at": booking.completed_at},
    )
    db.commit()
    db.refresh(payment)
    db.refresh(booking)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    return {
        "message": "Booking completed successfully",
        "booking": format_booking_detail_response(booking, db),
        "payment": format_payment_response(payment, db),
        "settlement": format_payment_settlement(settlement),
    }


async def confirm_customer_booking_complete_action(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    if current_user.role != "customer":
        raise HTTPException(
            status_code=403,
            detail="Only customers can confirm booking completion",
        )

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.customer_id == current_user.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking,
        [BookingStatus.awaiting_confirmation],
        "Only bookings waiting for confirmation can be completed",
    )
    direct_payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.customer_id == current_user.id,
            models.Payment.payment_stage == "service_fee",
            models.Payment.status == PaymentStatus.paid,
        )
        .order_by(models.Payment.created_at.desc(), models.Payment.id.desc())
        .first()
    )
    if direct_payment:
        return await _complete_direct_paid_booking(booking, direct_payment, current_user, db)
    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.customer_id == current_user.id,
            models.Payment.status == PaymentStatus.authorized,
        )
        .with_for_update()
        .order_by(models.Payment.created_at.desc(), models.Payment.id.desc())
        .first()
    )
    if not payment:
        existing_paid = (
            db.query(models.Payment)
            .filter(
                models.Payment.booking_id == booking.id,
                models.Payment.customer_id == current_user.id,
                models.Payment.status == PaymentStatus.paid,
            )
            .first()
        )
        if existing_paid and booking.status == BookingStatus.completed:
            return {
                "message": "Booking completion was already confirmed",
                "booking": format_booking_detail_response(booking, db),
                "payment": format_payment_response(existing_paid, db),
            }
        raise HTTPException(
            status_code=409,
            detail="An authorized payment is required before completing this booking",
        )

    if booking.quote_amount is None:
        raise HTTPException(status_code=400, detail="Booking has no final quote amount")
    if Decimal(str(payment.amount)).quantize(Decimal("0.01")) != Decimal(
        str(booking.quote_amount)
    ).quantize(Decimal("0.01")):
        if not payment.iyzico_payment_id or not payment.conversation_id:
            raise HTTPException(status_code=409, detail="Authorized payment reference is missing")
        try:
            void_result = await iyzico_service.get_iyzico_client().cancel_payment(
                payment.iyzico_payment_id, payment.conversation_id
            )
        except iyzico_service.IyzicoClientError as exc:
            payment.external_status = "void_failed"
            payment.failure_code = "void_failed"
            payment.failure_message = str(exc)
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        if str(void_result.get("status", "")).lower() != "success":
            payment.external_status = "void_failed"
            payment.failure_code = str(void_result.get("errorCode") or "void_failed")
            payment.failure_message = str(
                void_result.get("errorMessage") or "iyzico rejected the authorization release"
            )
            db.commit()
            raise HTTPException(status_code=502, detail=payment.failure_message)

        payment.status = PaymentStatus.voided
        payment.voided_at = utc_now()
        payment.external_status = "voided"
        payment_idempotency_key = f"reprice-{booking.id}-{uuid4().hex}"
        replacement = models.Payment(
            booking_id=booking.id,
            customer_id=current_user.id,
            provider_profile_id=booking.provider_profile_id,
            amount=booking.quote_amount,
            currency=payment.currency,
            status=PaymentStatus.processing,
            payment_method="iyzico_checkout",
            idempotency_key=payment_idempotency_key,
            conversation_id=f"booking-{booking.id}-payment-{uuid4().hex}",
            basket_id=None,
            created_at=utc_now(),
        )
        replacement.basket_id = replacement.conversation_id
        replacement.processing_started_at = utc_now()
        db.add(replacement)
        db.flush()
        try:
            preauth_result = await iyzico_service.get_iyzico_client().initialize_checkout_form_preauth(
                _build_checkout_payload(booking, replacement, current_user, db)
            )
        except iyzico_service.IyzicoClientError as exc:
            replacement.status = PaymentStatus.failed
            replacement.failure_code = "checkout_initialize_failed"
            replacement.failure_message = str(exc)
            replacement.failed_at = utc_now()
            booking.status = BookingStatus.awaiting_payment
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        token = preauth_result.get("token")
        checkout_url = preauth_result.get("paymentPageUrl")
        if str(preauth_result.get("status", "")).lower() != "success" or not token or not checkout_url:
            replacement.status = PaymentStatus.failed
            replacement.failure_code = str(preauth_result.get("errorCode") or "checkout_initialize_failed")
            replacement.failure_message = str(
                preauth_result.get("errorMessage") or "iyzico checkout initialization failed"
            )
            replacement.failed_at = utc_now()
            booking.status = BookingStatus.awaiting_payment
            db.commit()
            raise HTTPException(status_code=502, detail=replacement.failure_message)
        replacement.status = PaymentStatus.checkout_created
        replacement.checkout_expires_at = utc_now() + timedelta(seconds=IYZICO_CHECKOUT_TTL_SECONDS)
        replacement.iyzico_token = str(token)
        replacement.checkout_url = str(checkout_url)
        replacement.external_status = "checkout_created"
        booking.status = BookingStatus.awaiting_payment
        booking.status_note = "Final quote changed; customer must authorize the new amount"
        db.commit()
        db.refresh(replacement)
        db.refresh(booking)
        return {
            "message": "Final quote changed. Authorize the new amount before completing the booking.",
            "payment": format_payment_response(replacement, db),
            "booking": format_booking_detail_response(booking, db),
            "payment_page_url": replacement.checkout_url,
            "token": replacement.iyzico_token,
        }

    if not payment.iyzico_payment_id or not payment.conversation_id:
        raise HTTPException(status_code=409, detail="Authorized payment reference is missing")
    try:
        postauth_result = await iyzico_service.get_iyzico_client().post_auth(
            payment.iyzico_payment_id,
            payment.conversation_id,
            float(payment.amount),
        )
    except iyzico_service.IyzicoClientError as exc:
        payment.status = PaymentStatus.capture_failed
        payment.capture_failed_at = utc_now()
        payment.external_status = "postauth_failed"
        payment.failure_code = "postauth_failed"
        payment.failure_message = str(exc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if str(postauth_result.get("status", "")).lower() != "success":
        payment.status = PaymentStatus.capture_failed
        payment.capture_failed_at = utc_now()
        payment.external_status = "postauth_failed"
        payment.failure_code = str(postauth_result.get("errorCode") or "postauth_failed")
        payment.failure_message = str(
            postauth_result.get("errorMessage") or "iyzico rejected the capture"
        )
        db.commit()
        raise HTTPException(status_code=502, detail=payment.failure_message)

    transactions = postauth_result.get("itemTransactions") or []
    transaction = transactions[0] if transactions and isinstance(transactions[0], dict) else None
    if transaction and transaction.get("paymentTransactionId"):
        payment.payment_transaction_id = str(transaction["paymentTransactionId"])
    elif postauth_result.get("paymentTransactionId"):
        payment.payment_transaction_id = str(postauth_result["paymentTransactionId"])
    now = utc_now()
    payment.status = PaymentStatus.paid
    payment.paid_at = now
    payment.capture_failed_at = None
    payment.external_status = "success"
    payment.failure_code = None
    payment.failure_message = None
    latest_revision = (
        db.query(models.BookingQuoteRevision)
        .filter(models.BookingQuoteRevision.booking_id == booking.id)
        .order_by(models.BookingQuoteRevision.revision_number.desc())
        .first()
    )
    if latest_revision:
        latest_revision.customer_confirmed_at = now
        latest_revision.used_for_payment_at = now
    settlement = ensure_payment_settlement(payment, db, transaction=transaction)
    old_status = booking.status
    booking.status = BookingStatus.completed
    booking.completed_at = utc_now()
    booking.status_note = "Customer confirmed service completion"
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer confirmed service completion",
        booking.status_note,
        db,
        {"completed_at": booking.completed_at},
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Completion confirmed",
            "A customer confirmed your completed service",
            NotificationType.booking_completion_confirmed,
            NotificationRelatedType.booking,
            booking.id,
            db,
        )

    result = save_booking(booking, db)
    db.commit()
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    result["booking"] = format_booking_detail_response(booking, db)
    result["payment"] = format_payment_response(payment, db)
    result["settlement"] = format_payment_settlement(settlement)
    result["message"] = "Booking completed successfully"

    from backend.tasks.marketplace_tasks import enqueue_payment_settlement

    enqueue_payment_settlement(payment.id)

    return result


async def reject_customer_booking_complete_action(
    booking_id: int,
    status_note: str,
    current_user: models.User,
    db: Session,
):
    if current_user.role != "customer":
        raise HTTPException(
            status_code=403,
            detail="Only customers can reject booking completion",
        )

    if not status_note.strip():
        raise HTTPException(status_code=400, detail="Status note cannot be empty")

    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.customer_id == current_user.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    ensure_booking_status(
        booking,
        [BookingStatus.awaiting_confirmation],
        "Only bookings waiting for confirmation can be rejected",
    )
    old_status = booking.status
    booking.status = BookingStatus.accepted
    booking.status_note = status_note.strip()
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer rejected service completion",
        booking.status_note,
        db,
        {"reason": booking.status_note},
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )
    if provider_profile:
        create_notification(
            provider_profile.user_id,
            "Completion rejected",
            "A customer rejected your completion confirmation",
            NotificationType.booking_completion_rejected,
            NotificationRelatedType.booking,
            booking.id,
            db,
        )

    result = save_booking(booking, db)
    if booking_status_chat_message:
        db.refresh(booking_status_chat_message)
        await push_chat_message_to_room_members(booking_status_chat_message, db)
    result["booking"] = format_booking_detail_response(booking, db)
    result["message"] = "Completion confirmation rejected"

    return result
