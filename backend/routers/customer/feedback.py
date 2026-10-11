"""Customer API.

Customer-facing endpoints: profile, favorites, chat, bookings, payments, refunds, complaints, reviews.
Booking state changes live in `utils/customer_booking_actions.py`; routers handle params and auth.
"""

from datetime import datetime, timezone
from fastapi import Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from backend import models
from backend.ai.tools import create_chat_room_tool
from backend.auth import get_db, require_customer
from backend.constants import ALLOWED_PROVIDER_TAGS
from backend.core.clock import utc_now
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
from backend.utils.complaint import (
    add_complaint_status_history,
    format_complaint_response,
)
from backend.utils.customer_booking_actions import (
    accept_customer_booking_quote_action,
    appeal_customer_refund_request_action,
    cancel_customer_booking_action,
    confirm_customer_booking_complete_action,
    create_customer_booking_action,
    create_customer_refund_request_action,
    reject_customer_booking_complete_action,
    reject_customer_booking_quote_action,
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

@router.post("/bookings/{booking_id}/complaints")
def create_complaint(
    booking_id: int,
    complaint_data: ComplaintCreate,
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
        [
            BookingStatus.accepted,
            BookingStatus.refunding,
            BookingStatus.awaiting_confirmation,
            BookingStatus.completed,
        ],
        "Only active, refunding or completed bookings can be complained about",
    )
    existing_open_complaint = (
        db.query(models.Complaint)
        .filter(
            models.Complaint.booking_id == booking.id,
            models.Complaint.status == ComplaintStatus.open,
        )
        .first()
    )
    if existing_open_complaint:
        raise HTTPException(
            status_code=400, detail="This booking already has an open complaint"
        )
    complaint = models.Complaint(
        booking_id=booking.id,
        customer_id=current_user.id,
        reason=complaint_data.reason,
        status=ComplaintStatus.open,
        admin_note=None,
        created_at=utc_now(),
        resolved_at=None,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    add_complaint_status_history(
        complaint, "created", complaint.status, complaint.reason, current_user, db
    )
    create_admin_notifications(
        "New complaint",
        "A customer submitted a new complaint",
        NotificationType.complaint_created,
        NotificationRelatedType.complaint,
        complaint.id,
        db,
    )
    db.commit()
    return success_response(
        {
            "message": "Complaint created successfully",
            "complaint": format_complaint_response(complaint, db),
        }
    )


@router.get("/customer/complaints")
def get_customer_complaints(
    status: ComplaintStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    query = db.query(models.Complaint).filter(
        models.Complaint.customer_id == current_user.id
    )
    if status:
        query = query.filter(models.Complaint.status == status)
    query = query.order_by(models.Complaint.created_at.desc())
    complaints, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for complaint in complaints:
        result.append(format_complaint_response(complaint, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.post("/bookings/{booking_id}/review")
def create_review(
    booking_id: int,
    review_data: ReviewCreate,
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
    if booking.status != BookingStatus.completed:
        raise HTTPException(
            status_code=400, detail="Only completed bookings can be reviewed"
        )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    if provider_profile.user_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="You cannot review your own provider profile"
        )
    existing_review = (
        db.query(models.Review).filter(models.Review.booking_id == booking.id).first()
    )
    if existing_review:
        raise HTTPException(
            status_code=400, detail="This booking has already been reviewed"
        )
    new_review = models.Review(
        booking_id=booking.id,
        customer_id=current_user.id,
        provider_profile_id=booking.provider_profile_id,
        rating=review_data.rating,
        comment=review_data.comment,
        created_at=utc_now(),
        is_visible=1,
    )
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    embedding_task_id = enqueue_review_embedding_sync(new_review, db, current_user.id)
    return success_response(
        {
            "message": "Review created successfully",
            "embedding_task_id": embedding_task_id,
            "review": format_review_detail_response(new_review, db),
        }
    )


@router.get("/customer/reviews")
def get_customer_reviews(
    is_visible: bool | None = True,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    query = db.query(models.Review).filter(models.Review.customer_id == current_user.id)
    if is_visible is not None:
        query = query.filter(models.Review.is_visible == (1 if is_visible else 0))
    query = query.order_by(models.Review.created_at.desc())
    reviews, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for review in reviews:
        result.append(format_review_detail_response(review, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.put("/reviews/{review_id}")
def update_review(
    review_id: int,
    review_data: ReviewUpdate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    review = (
        db.query(models.Review)
        .filter(
            models.Review.id == review_id,
            models.Review.customer_id == current_user.id,
            models.Review.is_visible == 1,
        )
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.rating = review_data.rating
    review.comment = review_data.comment
    db.commit()
    db.refresh(review)
    embedding_task_id = enqueue_review_embedding_sync(review, db, current_user.id)
    return success_response(
        {
            "message": "Review updated successfully",
            "embedding_task_id": embedding_task_id,
            "review": format_review_detail_response(review, db),
        }
    )


@router.delete("/reviews/{review_id}")
def delete_review(
    review_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    review = (
        db.query(models.Review)
        .filter(
            models.Review.id == review_id,
            models.Review.customer_id == current_user.id,
            models.Review.is_visible == 1,
        )
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.is_visible = 0
    db.commit()
    db.refresh(review)
    embedding_task_id = enqueue_review_embedding_delete(review, db, current_user.id)
    return success_response(
        {
            "message": "Review deleted successfully",
            "embedding_task_id": embedding_task_id,
        }
    )
