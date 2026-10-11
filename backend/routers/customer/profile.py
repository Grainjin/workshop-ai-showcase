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
from backend.utils.service_locations import apply_profile_location
from backend.utils.verification import apply_phone_number_change
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
    CustomerProfilePatch,
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


@router.post("/customer/profile")
def create_customer_profile(
    profile_data: CustomerProfileCreate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    existing_profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )
    if existing_profile:
        raise HTTPException(status_code=400, detail="Customer profile already exists")
    new_profile = models.CustomerProfile(
        user_id=current_user.id,
        phone_number=profile_data.phone_number,
        address=profile_data.address,
        service_province=profile_data.service_province,
        service_location_id=profile_data.service_location_id,
        latitude=profile_data.latitude,
        longitude=profile_data.longitude,
        current_address=profile_data.current_address,
        current_latitude=profile_data.current_latitude,
        current_longitude=profile_data.current_longitude,
        default_service_address=profile_data.default_service_address,
        default_service_latitude=profile_data.default_service_latitude,
        default_service_longitude=profile_data.default_service_longitude,
        notes=profile_data.notes,
    )
    db.add(new_profile)
    apply_profile_location(db=db, profile=new_profile, location_id=profile_data.service_location_id)
    db.commit()
    db.refresh(new_profile)
    return success_response(
        {
            "message": "Customer profile created successfully",
            "profile": format_customer_profile_response(new_profile),
        }
    )


@router.get("/customer/profile")
def get_customer_profile(
    current_user: models.User = Depends(require_customer), db: Session = Depends(get_db)
):
    profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Customer profile not found")
    return success_response(format_customer_profile_response(profile))


@router.put("/customer/profile/service-province")
def update_customer_service_province(
    province_data: CustomerServiceProvinceUpdate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )
    message = "Customer service province updated successfully"
    if not profile:
        profile = models.CustomerProfile(
            user_id=current_user.id,
            phone_number="",
            address="",
            service_province=province_data.service_province,
            latitude=None,
            longitude=None,
            current_address=None,
            current_latitude=None,
            current_longitude=None,
            default_service_address=None,
            default_service_latitude=None,
            default_service_longitude=None,
            notes=None,
        )
        db.add(profile)
        message = "Customer profile created with service province"
    else:
        profile.service_province = province_data.service_province
    if province_data.service_location_id is not None:
        apply_profile_location(
            db=db,
            profile=profile,
            location_id=province_data.service_location_id,
        )
    else:
        profile.service_location_id = None

    db.commit()
    db.refresh(profile)
    return success_response(
        {
            "message": message,
            "profile": format_customer_profile_response(profile),
        }
    )


@router.put("/customer/profile")
def update_customer_profile(
    profile_data: CustomerProfileCreate,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )
    message = "Customer profile updated successfully"
    if not profile:
        profile = models.CustomerProfile(user_id=current_user.id)
        db.add(profile)
        message = "Customer profile created successfully"

    apply_phone_number_change(current_user, profile.phone_number, profile_data.phone_number)
    profile.phone_number = profile_data.phone_number
    profile.address = profile_data.address
    profile.service_province = profile_data.service_province
    profile.service_location_id = profile_data.service_location_id
    profile.latitude = profile_data.latitude
    profile.longitude = profile_data.longitude
    profile.current_address = profile_data.current_address
    profile.current_latitude = profile_data.current_latitude
    profile.current_longitude = profile_data.current_longitude
    profile.default_service_address = profile_data.default_service_address
    profile.default_service_latitude = profile_data.default_service_latitude
    profile.default_service_longitude = profile_data.default_service_longitude
    profile.notes = profile_data.notes
    apply_profile_location(
        db=db,
        profile=profile,
        location_id=profile_data.service_location_id,
    )
    db.commit()
    db.refresh(profile)
    return success_response(
        {
            "message": message,
            "profile": format_customer_profile_response(profile),
        }
    )


@router.patch("/customer/profile")
def patch_customer_profile(
    profile_data: CustomerProfilePatch,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )
    message = "Customer profile updated successfully"
    if not profile:
        profile = models.CustomerProfile(
            user_id=current_user.id,
            phone_number="",
            address="",
            service_province="",
            latitude=None,
            longitude=None,
            current_address=None,
            current_latitude=None,
            current_longitude=None,
            default_service_address=None,
            default_service_latitude=None,
            default_service_longitude=None,
            notes=None,
        )
        db.add(profile)
        message = "Customer profile created successfully"

    previous_phone = profile.phone_number
    updates = profile_data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field != "service_location_id":
            setattr(profile, field, value)
    if "service_location_id" in updates:
        profile.service_location_id = updates["service_location_id"]
        if profile.service_location_id is not None:
            apply_profile_location(
                db=db,
                profile=profile,
                location_id=profile.service_location_id,
            )
    elif "service_province" in updates:
        profile.service_location_id = None
    apply_phone_number_change(current_user, previous_phone, profile.phone_number)

    db.commit()
    db.refresh(profile)
    return success_response(
        {
            "message": message,
            "profile": format_customer_profile_response(profile),
        }
    )
