"""Customer API.

Customer-facing endpoints: profile, favorites, chat, bookings, payments, refunds, complaints, reviews.
Booking state changes live in `utils/customer_booking_actions.py`; routers handle params and auth.
"""

from datetime import datetime, timezone
from fastapi import Depends, File, Form, HTTPException, Query, UploadFile
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
from backend.utils.availability import (
    ensure_provider_available_for_datetime_range,
    is_provider_open_now,
)
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
from backend.utils.service_locations import format_service_area
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

def format_customer_search_history_response(history: models.CustomerSearchHistory):
    return {
        "id": history.id,
        "customer_id": history.customer_id,
        "last_provider_profile_id": history.last_provider_profile_id,
        "last_provider_tag": history.last_provider_tag,
        "updated_at": history.updated_at,
    }


@router.get(
    "/customer/home/recommendations",
    response_model=ApiResponse[CustomerHomeRecommendationResponseData],
)
def get_customer_home_recommendations(
    service_province: str | None = None,
    service_location_id: int | None = Query(default=None, gt=0),
    provider_tag: str | None = None,
    limit: int = 20,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    if provider_tag and provider_tag not in ALLOWED_PROVIDER_TAGS:
        raise HTTPException(status_code=400, detail=f"Unsupported tag: {provider_tag}")

    return success_response(
        build_customer_home_recommendations(
            current_user,
            db,
            service_province=service_province,
            service_location_id=service_location_id,
            provider_tag=provider_tag,
            limit=limit,
        )
    )


@router.get(
    "/customer/providers/search",
    response_model=ApiResponse[CustomerProviderSearchResponseData],
)
def search_customer_provider_profiles(
    keyword: str,
    service_province: str | None = None,
    service_location_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=40, ge=1, le=100),
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    max_distance_km: float | None = Query(default=None, gt=0),
    scheduled_start_time: datetime | None = None,
    scheduled_end_time: datetime | None = None,
    tags: list[str] | None = Query(default=None),
    sort_by: str | None = None,
    min_rating: float | None = Query(default=None, ge=0, le=5),
    is_open: bool | None = None,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    return success_response(
        search_customer_providers(
            current_user,
            db,
            keyword,
            service_province=service_province,
            service_location_id=service_location_id,
            limit=limit,
            min_price=min_price,
            max_price=max_price,
            latitude=latitude,
            longitude=longitude,
            max_distance_km=max_distance_km,
            scheduled_start_time=scheduled_start_time,
            scheduled_end_time=scheduled_end_time,
            tags=tags,
            sort_by=sort_by,
            min_rating=min_rating,
            is_open=is_open,
        )
    )


@router.get(
    "/customer/providers/{provider_id}",
    response_model=ApiResponse[CustomerProviderDetailResponseData],
)
def get_customer_provider_detail(
    provider_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(
            models.ProviderProfile.id == provider_id,
            models.ProviderProfile.qualification_verification_status
            == ProviderVerificationStatus.approved,
        )
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider not found")

    history = save_customer_provider_tag_history(
        current_user.id,
        provider_profile,
        db,
    )
    provider_data = format_provider_profile_with_rating(provider_profile, db)
    service_area_rows = (
        db.query(models.ProviderServiceArea, models.ServiceLocation)
        .join(
            models.ServiceLocation,
            models.ServiceLocation.id == models.ProviderServiceArea.service_location_id,
        )
        .filter(models.ProviderServiceArea.provider_profile_id == provider_profile.id)
        .order_by(models.ServiceLocation.name.asc())
        .all()
    )
    provider_data.update(
        {
            "is_open": is_provider_open_now(provider_profile.id, db),
            "service_areas": [
                format_service_area(db, location) for _, location in service_area_rows
            ],
            "is_favorited": db.query(models.FavoriteProvider.id)
            .filter(
                models.FavoriteProvider.customer_id == current_user.id,
                models.FavoriteProvider.provider_profile_id == provider_profile.id,
            )
            .first()
            is not None,
        }
    )
    return success_response(
        {
            "provider": provider_data,
            "history": format_customer_search_history_response(history),
        }
    )


@router.post("/customer/favorites/{provider_profile_id}")
def add_favorite_provider(
    provider_profile_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == provider_profile_id)
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    if provider_profile.qualification_verification_status != "approved":
        raise HTTPException(
            status_code=400, detail="Only approved providers can be favorited"
        )
    existing_favorite = (
        db.query(models.FavoriteProvider)
        .filter(
            models.FavoriteProvider.customer_id == current_user.id,
            models.FavoriteProvider.provider_profile_id == provider_profile_id,
        )
        .first()
    )
    if existing_favorite:
        raise HTTPException(status_code=400, detail="Provider is already in favorites")
    favorite = models.FavoriteProvider(
        customer_id=current_user.id,
        provider_profile_id=provider_profile_id,
        created_at=utc_now(),
    )
    db.add(favorite)
    db.commit()
    db.refresh(favorite)
    return success_response(
        {
            "message": "Provider added to favorites successfully",
            "favorite": format_favorite_provider_response(favorite, db),
        }
    )


@router.get("/customer/favorites")
def get_favorite_providers(
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.FavoriteProvider)
        .filter(models.FavoriteProvider.customer_id == current_user.id)
        .order_by(models.FavoriteProvider.created_at.desc())
    )
    favorites, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for favorite in favorites:
        result.append(format_favorite_provider_response(favorite, db))
    return success_response(build_paginated_response(result, total, page, page_size))


@router.delete("/customer/favorites/{provider_profile_id}")
def remove_favorite_provider(
    provider_profile_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    favorite = (
        db.query(models.FavoriteProvider)
        .filter(
            models.FavoriteProvider.customer_id == current_user.id,
            models.FavoriteProvider.provider_profile_id == provider_profile_id,
        )
        .first()
    )
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite provider not found")
    db.delete(favorite)
    db.commit()
    return success_response({"message": "Provider removed from favorites successfully"})


@router.post("/customer/chats/{provider_profile_id}")
def open_chat_with_provider(
    provider_profile_id: int,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == provider_profile_id)
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    if provider_profile.qualification_verification_status != "approved":
        raise HTTPException(status_code=403, detail="Provider qualification approval is required")
    return success_response(
        create_chat_room_tool(provider_profile_id, current_user, db)
    )


@router.get("/customer/chats")
def get_customer_chats(
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models.ChatRoom)
        .filter(models.ChatRoom.customer_id == current_user.id)
        .order_by(models.ChatRoom.last_message_at.desc().nullslast())
    )
    chat_rooms, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for chat_room in chat_rooms:
        result.append(
            format_chat_room_response_with_unread(chat_room, db, current_user)
        )
    return success_response(build_paginated_response(result, total, page, page_size))


