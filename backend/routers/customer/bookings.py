"""Customer API.

Customer-facing endpoints: profile, favorites, chat, bookings, payments, refunds, complaints, reviews.
Booking state changes live in `utils/customer_booking_actions.py`; routers handle params and auth.
"""

from datetime import datetime, timezone
from fastapi import Depends, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from backend import models
from backend.ai.tools import create_chat_room_tool
from backend.auth import get_db, require_customer
from backend.constants import ALLOWED_PROVIDER_TAGS
from backend.core.clock import to_workshop_datetime, utc_now
from backend.utils.booking import (
    add_booking_status_history,
    ensure_booking_status,
    format_booking_detail_response,
)
from backend.utils.availability import ensure_provider_available_for_datetime_range
from backend.utils.chat import (
    create_booking_status_chat_message,
    format_chat_message_response,
    format_chat_room_response_with_unread,
    push_chat_message_to_room_members,
)
from backend.utils.payment_redirect import payment_result_url_for_request
from backend.utils.complaint import (
    add_complaint_status_history,
    format_complaint_response,
)
from backend.utils.customer_booking_actions import (
    accept_customer_final_quote_action,
    accept_customer_booking_quote_action,
    appeal_customer_refund_request_action,
    cancel_customer_booking_action,
    confirm_customer_booking_complete_action,
    create_customer_booking_action,
    create_customer_refund_request_action,
    reject_customer_booking_complete_action,
    reject_customer_booking_quote_action,
    reject_customer_final_quote_action,
    close_final_quote_negotiation_action,
    pay_customer_booking_action,
)
from backend.utils.customer_recommendation import (
    build_customer_home_recommendations,
    save_customer_provider_tag_history,
    search_customer_providers,
)
from backend.utils.formatters import format_customer_profile_response
from backend.utils.notification import create_admin_notifications, create_notification
from backend.utils.pagination import build_paginated_response, paginate_query
from backend.utils.payment import format_payment_response
from backend.utils.provider import (
    format_favorite_provider_response,
    format_provider_profile_with_rating,
)
from backend.utils.refund import (
    add_refund_request_status_history,
    ensure_refund_can_restore_previous_booking_status,
    format_refund_request_response,
)
from backend.utils.review import format_review_detail_response
from backend.utils.review_embedding_queue import (
    enqueue_review_embedding_delete,
    enqueue_review_embedding_sync,
)
from backend.utils.router import ApiRouter
from backend.utils.demo_mode import reject_demo_restricted_action
from backend.schemas import (
    ApiResponse,
    BookingCreate,
    BookingCreateResponseData,
    BookingNoteUpdate,
    BookingStatus,
    BookingUpdate,
    BookingUpdateResponseData,
    ComplaintCreate,
    ComplaintStatus,
    CustomerHomeRecommendationResponseData,
    CustomerProviderDetailResponseData,
    CustomerProviderSearchResponseData,
    CustomerProfileCreate,
    CustomerServiceProvinceUpdate,
    NotificationRelatedType,
    NotificationType,
    PaymentCreate,
    PaymentStatus,
    ProviderVerificationStatus,
    RefundRequestCreate,
    RefundAppealCreate,
    RefundRequestStatus,
    ReviewCreate,
    ReviewUpdate,
)
from backend.utils.response import success_response

router = ApiRouter(tags=["Customer"])

@router.post("/bookings", response_model=ApiResponse[BookingCreateResponseData])
async def create_booking(
    provider_profile_id: int = Form(...),
    service_category: str = Form(...),
    title: str = Form(...),
    service_description: str = Form(...),
    service_address: str = Form(...),
    service_latitude: float = Form(...),
    service_longitude: float = Form(...),
    customer_current_address: str | None = Form(default=None),
    customer_current_latitude: float | None = Form(default=None),
    customer_current_longitude: float | None = Form(default=None),
    scheduled_start_time: datetime = Form(...),
    scheduled_end_time: datetime = Form(...),
    chat_room_id: int | None = Form(default=None),
    attachments: list[UploadFile] | None = File(default=None),
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    if attachments:
        reject_demo_restricted_action(current_user, "booking_upload")
    try:
        booking_data = BookingCreate(
            provider_profile_id=provider_profile_id,
            chat_room_id=chat_room_id,
            title=title,
            service_category=service_category,
            service_description=service_description,
            service_address=service_address,
            service_latitude=service_latitude,
            service_longitude=service_longitude,
            customer_current_address=customer_current_address,
            customer_current_latitude=customer_current_latitude,
            customer_current_longitude=customer_current_longitude,
            scheduled_start_time=scheduled_start_time,
            scheduled_end_time=scheduled_end_time,
        )
    except ValidationError as exc:
        errors = [
            {
                "loc": error.get("loc"),
                "msg": error.get("msg"),
                "type": error.get("type"),
            }
            for error in exc.errors()
        ]
        raise HTTPException(status_code=422, detail=errors) from exc

    return success_response(
        await create_customer_booking_action(
            booking_data,
            current_user,
            db,
            attachments=attachments,
        )
    )


@router.get("/customer/bookings")
def get_customer_bookings(
    status: BookingStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    query = db.query(models.Booking).filter(
        models.Booking.customer_id == current_user.id
    )
    if status:
        query = query.filter(models.Booking.status == status)
    query = query.order_by(models.Booking.booking_at.desc())
    bookings, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for booking in bookings:
        result.append(format_booking_detail_response(booking, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.put(
    "/customer/bookings/{booking_id}",
    response_model=ApiResponse[BookingUpdateResponseData],
)
async def update_pending_booking(
    booking_id: int,
    booking_data: BookingUpdate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
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
        [BookingStatus.pending],
        "Only pending bookings can be updated before provider response",
    )
    scheduled_start_time = to_workshop_datetime(booking_data.scheduled_start_time)
    scheduled_end_time = to_workshop_datetime(booking_data.scheduled_end_time)
    ensure_provider_available_for_datetime_range(
        booking.provider_profile_id,
        scheduled_start_time,
        scheduled_end_time,
        db,
    )

    old_status = booking.status
    booking.service_description = booking_data.service_description
    booking.title = booking_data.title
    booking.service_address = booking_data.service_address
    booking.service_latitude = booking_data.service_latitude
    booking.service_longitude = booking_data.service_longitude
    booking.customer_current_address = booking_data.customer_current_address
    booking.customer_current_latitude = booking_data.customer_current_latitude
    booking.customer_current_longitude = booking_data.customer_current_longitude
    booking.scheduled_start_time = scheduled_start_time
    booking.scheduled_end_time = scheduled_end_time
    booking.status_note = "Customer updated booking request"

    add_booking_status_history(
        booking,
        old_status,
        booking.status,
        booking.status_note,
        current_user,
        db,
    )
    chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer updated the booking request",
        booking.status_note,
        db,
        {
            "service_description": booking.service_description,
            "service_address": booking.service_address,
            "service_latitude": booking.service_latitude,
            "service_longitude": booking.service_longitude,
            "customer_current_address": booking.customer_current_address,
            "customer_current_latitude": booking.customer_current_latitude,
            "customer_current_longitude": booking.customer_current_longitude,
            "scheduled_start_time": booking.scheduled_start_time,
            "scheduled_end_time": booking.scheduled_end_time,
            "status": booking.status,
        },
    )

    db.commit()
    db.refresh(booking)

    formatted_chat_message = None
    if chat_message:
        db.refresh(chat_message)
        await push_chat_message_to_room_members(chat_message, db)
        formatted_chat_message = format_chat_message_response(chat_message, db)

    return success_response(
        {
            "message": "Booking updated successfully",
            "booking": format_booking_detail_response(booking, db),
            "chat_message": formatted_chat_message,
        },
        message="Booking updated successfully",
    )


@router.put("/customer/bookings/{booking_id}/pay")
async def pay_booking_by_booking_id(
    booking_id: int,
    payment_data: PaymentCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await pay_customer_booking_action(
            booking_id,
            payment_data.payment_method,
            current_user,
            db,
            idempotency_key=idempotency_key,
            payment_stage=payment_data.payment_stage.value,
            frontend_return_url=payment_result_url_for_request(request),
        )
    )


@router.get("/customer/payments")
def get_customer_payments(
    status: PaymentStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    query = db.query(models.Payment).filter(
        models.Payment.customer_id == current_user.id
    )
    if status:
        query = query.filter(models.Payment.status == status)
    query = query.order_by(models.Payment.created_at.desc())
    payments, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for payment in payments:
        result.append(format_payment_response(payment, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.post("/bookings/{booking_id}/refund-requests")
async def create_refund_request(
    booking_id: int,
    refund_data: RefundRequestCreate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await create_customer_refund_request_action(
            booking_id,
            refund_data.reason,
            current_user,
            db,
            refund_data.refund_amount,
        )
    )


@router.get("/customer/refund-requests")
def get_customer_refund_requests(
    status: RefundRequestStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    query = db.query(models.RefundRequest).filter(
        models.RefundRequest.customer_id == current_user.id
    )
    if status:
        query = query.filter(models.RefundRequest.status == status)
    query = query.order_by(models.RefundRequest.created_at.desc())
    refund_requests, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for refund_request in refund_requests:
        result.append(format_refund_request_response(refund_request, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.put("/refund-requests/{refund_request_id}/cancel")
async def cancel_refund_request(
    refund_request_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
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
    if refund_request.status not in [
        RefundRequestStatus.pending,
        RefundRequestStatus.rejected,
    ]:
        raise HTTPException(
            status_code=400,
            detail="Only pending or rejected refund requests can be cancelled",
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
        "Only refunding bookings can cancel a refund request",
    )
    old_status = booking.status
    old_refund_status = refund_request.status
    refund_request.status = RefundRequestStatus.cancelled
    refund_request.cancelled_at = utc_now()
    ensure_refund_can_restore_previous_booking_status(refund_request)
    booking.status = refund_request.previous_booking_status
    booking.status_note = "Customer cancelled refund request"
    add_booking_status_history(
        booking, old_status, booking.status, booking.status_note, current_user, db
    )
    booking_status_chat_message = create_booking_status_chat_message(
        booking,
        old_status,
        current_user.id,
        "Customer cancelled the refund request",
        booking.status_note,
        db,
        {
            "refund_request_id": refund_request.id,
            "refund_status": refund_request.status,
            "restored_booking_status": booking.status,
            "cancelled_at": refund_request.cancelled_at,
        },
    )
    add_refund_request_status_history(
        refund_request,
        old_refund_status,
        refund_request.status,
        "Customer cancelled refund request",
        current_user,
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
            "Refund request cancelled",
            "A customer cancelled a refund request",
            NotificationType.refund_cancelled,
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
    return success_response(
        {
            "message": "Refund request cancelled successfully",
            "refund_request": format_refund_request_response(refund_request, db),
            "booking": format_booking_detail_response(booking, db),
        }
    )


@router.put("/refund-requests/{refund_request_id}/appeal")
async def appeal_refund_request(
    refund_request_id: int,
    appeal_data: RefundAppealCreate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await appeal_customer_refund_request_action(
            refund_request_id,
            appeal_data,
            current_user,
            db,
        )
    )


@router.put("/customer/bookings/{booking_id}/reject-quote")
async def reject_booking_quote(
    booking_id: int,
    note_data: BookingNoteUpdate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await reject_customer_booking_quote_action(
            booking_id,
            note_data.status_note,
            current_user,
            db,
        )
    )


@router.put("/customer/bookings/{booking_id}/accept-quote")
async def accept_booking_quote(
    booking_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await accept_customer_booking_quote_action(
            booking_id,
            current_user,
            db,
        )
    )


@router.put("/customer/bookings/{booking_id}/accept-final-quote")
async def accept_final_quote(
    booking_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(await accept_customer_final_quote_action(booking_id, current_user, db))


@router.put("/customer/bookings/{booking_id}/reject-final-quote")
async def reject_final_quote(
    booking_id: int,
    note_data: BookingNoteUpdate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await reject_customer_final_quote_action(booking_id, note_data.status_note, current_user, db)
    )


@router.put("/customer/bookings/{booking_id}/close-final-quote")
async def close_final_quote(
    booking_id: int,
    note_data: BookingNoteUpdate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await close_final_quote_negotiation_action(booking_id, note_data.status_note, current_user, db)
    )


@router.put("/customer/bookings/{booking_id}/cancel")
async def cancel_booking(
    booking_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await cancel_customer_booking_action(
            booking_id,
            current_user,
            db,
        )
    )


@router.put("/customer/bookings/{booking_id}/confirm-complete")
async def confirm_booking_complete(
    booking_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await confirm_customer_booking_complete_action(
            booking_id,
            current_user,
            db,
        )
    )


@router.put("/customer/bookings/{booking_id}/reject-complete")
async def reject_booking_complete(
    booking_id: int,
    note_data: BookingNoteUpdate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        await reject_customer_booking_complete_action(
            booking_id,
            note_data.status_note,
            current_user,
            db,
        )
    )

