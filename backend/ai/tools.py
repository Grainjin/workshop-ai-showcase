"""AI tool business implementations.

Functions invoked by LangChain tools: search providers, summarize reviews, query bookings,
explain booking flow, and prepare pending user-confirmed actions. Reuses standard business utils
so AI follows the same status rules as regular APIs.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from backend import config, models
from backend.schemas import (
    BookingNoteUpdate,
    BookingCreate,
    BookingStatus,
    NotificationRelatedType,
    NotificationType,
    PaymentStatus,
    ProviderBookingQuoteCreate,
    ProviderRefundRejectCreate,
    RefundRequestStatus,
)
from backend.services.ai_service import (
    generate_embedding,
)
from backend.services.milvus_service import search_review_embeddings
from backend.utils.ai import (
    build_provider_review_context,
    build_provider_recommendations,
    enrich_review_context_with_provider_info,
    has_review_context,
    normalize_ai_recommendation_tags,
)
from backend.utils.ai_pending_action import create_ai_pending_action, format_provider_preview
from backend.utils.chat import (
    format_chat_room_response_with_unread,
    get_or_create_chat_room,
)
from backend.utils.booking import (
    ensure_booking_status,
    format_booking_detail_response,
    get_booking_for_user_or_404,
)
from backend.utils.availability import ensure_provider_available_for_datetime_range
from backend.utils.location import has_location
from backend.utils.provider_eligibility import require_provider_can_accept_orders
from backend.utils.notification import create_notification
from backend.utils.provider import get_provider_profile_for_user
from backend.utils.service_locations import resolve_location_context

PLATFORM_CAPABILITIES = [
    "Recommend providers by service need, e.g. cleaning, childcare, elderly care, electrician, plumbing, painter, locksmith, technician, moving.",
    "Summarize candidate provider reviews: price, attitude, highlights, and risks.",
    "Open a chat between customer and provider.",
    "Build booking drafts from customer descriptions and ask for missing address, schedule, or provider.",
    "Query booking status and explain quotes, payment, service, acceptance, refunds, complaints, and cancellation.",
    "Prepare cancel, refund, payment, and completion actions as confirmation cards — never executed directly.",
]


def get_platform_capabilities_tool(question: str | None = None):
    return {
        "question": question,
        "capabilities": PLATFORM_CAPABILITIES,
        "answer": "Here is what I can help with:\n"
        + "\n".join(
            f"{index}. {capability}"
            for index, capability in enumerate(PLATFORM_CAPABILITIES, start=1)
        ),
    }


BOOKING_STATUS_EXPLANATIONS = {
    "pending": {
        "label": "Awaiting provider quote",
        "meaning": "Customer created a booking request; provider has not quoted or rejected yet.",
        "next_actions": [
            "provider can submit a quote",
            "provider can reject the booking",
            "customer can cancel the booking",
        ],
    },
    "quoted": {
        "label": "Provider quoted",
        "meaning": "Provider gave a price; work has not started yet.",
        "next_actions": [
            "customer can pay and accept the quote",
            "customer can reject the quote; booking returns to pending",
            "customer can cancel the booking",
        ],
    },
    "accepted": {
        "label": "Paid, in progress",
        "meaning": "Customer paid; booking is active and provider can perform service.",
        "next_actions": [
            "provider can mark complete after service",
            "customer can request a refund",
            "customer can file a complaint",
        ],
    },
    "awaiting_confirmation": {
        "label": "Awaiting customer acceptance",
        "meaning": "Provider marked complete; waiting for customer acceptance.",
        "next_actions": [
            "customer can confirm completion",
            "customer can reject completion",
            "customer can request a refund",
            "customer can file a complaint",
        ],
    },
    "completed": {
        "label": "Completed",
        "meaning": "Customer confirmed completion; booking closed normally.",
        "next_actions": [
            "customer can leave a review",
            "customer can request a refund",
            "customer can file a complaint",
        ],
    },
    "refunding": {
        "label": "Refund in progress",
        "meaning": "Customer requested a refund; awaiting provider action.",
        "next_actions": [
            "provider can approve refund",
            "provider can reject refund with a reason",
            "customer can cancel refund request and restore prior status",
        ],
    },
    "refunded": {
        "label": "Refunded",
        "meaning": "Refund completed; booking closed.",
        "next_actions": [],
    },
    "cancelled": {
        "label": "Cancelled",
        "meaning": "Customer cancelled before payment was finalized.",
        "next_actions": [],
    },
    "rejected": {
        "label": "Provider rejected",
        "meaning": "Provider rejected the customer booking request.",
        "next_actions": [],
    },
}

BOOKING_FLOW_STEPS = [
    "Customer selects a provider from recommendations or the provider profile page.",
    "If not created from chat, the system creates a chat room and posts booking info.",
    "New bookings start as pending; provider gets a notification.",
    "Provider must quote to accept; booking becomes quoted.",
    "Customer can reject quote; booking returns to pending for a new quote.",
    "After accepting quote, booking is awaiting_payment with a payment record.",
    "Customer can cancel while pending, quoted, or awaiting_payment.",
    "After payment, booking becomes accepted and work can begin.",
    "Provider marks complete; booking becomes awaiting_confirmation.",
    "Customer acceptance moves booking to completed.",
    "Refunds are available after a paid booking is completed; complaints may be raised while service is in progress or after completion.",
    "Refund requests move to refunding; approved -> refunded; rejected stays refunding; customer can cancel refund.",
]


def get_customer_profile_for_ai_tool(current_user: models.User, db: Session):
    if current_user.role != "customer":
        return None

    return (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )


def search_providers_tool(
    query: str,
    service_tags: list[str],
    service_province: str | None,
    max_price: float | None,
    budget_preference: str | None,
    current_user: models.User | None,
    db: Session,
    latitude: float | None = None,
    longitude: float | None = None,
    max_distance_km: float | None = None,
    scheduled_start_time=None,
    scheduled_end_time=None,
    limit: int | None = 5,
    service_location_id: int | None = None,
):
    normalized_service_tags = normalize_ai_recommendation_tags(
        service_tags,
        query,
    )

    if not normalized_service_tags:
        return {
            "resolved_need": {
                "service_tags": [],
                "service_province": service_province,
                "service_location_id": service_location_id,
                "max_price": max_price,
                "budget_preference": budget_preference,
                "latitude": latitude,
                "longitude": longitude,
                "max_distance_km": max_distance_km,
                "scheduled_start_time": (
                    scheduled_start_time.isoformat()
                    if scheduled_start_time
                    else None
                ),
                "scheduled_end_time": (
                    scheduled_end_time.isoformat() if scheduled_end_time else None
                ),
            },
            "query": query,
            "service_province": service_province,
            "service_location_id": service_location_id,
            "max_price": max_price,
            "latitude": latitude,
            "longitude": longitude,
            "max_distance_km": max_distance_km,
            "scheduled_start_time": (
                scheduled_start_time.isoformat() if scheduled_start_time else None
            ),
            "scheduled_end_time": (
                scheduled_end_time.isoformat() if scheduled_end_time else None
            ),
            "recommendation_count": 0,
            "recommendations": [],
            "no_core_tag_matched": True,
            "message": (
                "No clear service type matched; it may be other local services."
                "Try searching providers on the home page."
            ),
        }

    customer_profile = (
        get_customer_profile_for_ai_tool(current_user, db) if current_user else None
    )

    resolved_service_province, resolved_service_location_id = resolve_location_context(
        db,
        requested_province=service_province,
        requested_location_id=service_location_id,
        profile_province=(
            customer_profile.service_province if customer_profile else None
        ),
        profile_location_id=(
            customer_profile.service_location_id if customer_profile else None
        ),
    )
    resolved_latitude = (
        latitude
        if latitude is not None
        else (customer_profile.latitude if customer_profile else None)
    )
    resolved_longitude = (
        longitude
        if longitude is not None
        else (customer_profile.longitude if customer_profile else None)
    )

    if max_distance_km is not None and not has_location(
        resolved_latitude,
        resolved_longitude,
    ):
        raise HTTPException(
            status_code=400,
            detail="max_distance_km requires latitude and longitude",
        )

    recommendations = build_provider_recommendations(
        query,
        normalized_service_tags,
        resolved_service_province,
        max_price,
        budget_preference,
        db,
        latitude=resolved_latitude,
        longitude=resolved_longitude,
        max_distance_km=max_distance_km,
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
        limit=limit,
        service_location_id=resolved_service_location_id,
    )

    return {
        "resolved_need": {
            "service_tags": normalized_service_tags,
            "normalized_service_tags": normalized_service_tags,
            "service_province": resolved_service_province,
            "service_location_id": resolved_service_location_id,
            "max_price": max_price,
            "budget_preference": budget_preference,
            "latitude": resolved_latitude,
            "longitude": resolved_longitude,
            "max_distance_km": max_distance_km,
            "scheduled_start_time": (
                scheduled_start_time.isoformat() if scheduled_start_time else None
            ),
            "scheduled_end_time": (
                scheduled_end_time.isoformat() if scheduled_end_time else None
            ),
        },
        **recommendations,
    }


def summarize_provider_reviews_tool(
    question: str,
    provider_ids: list[int],
    current_user: models.User,
    db: Session,
):
    if config.DEMO_MODE:
        return {
            "answer": "I found relevant review data.",
            "review_context_source": "database",
            "review_context": build_provider_review_context(provider_ids, db),
        }
    review_context_source = "milvus"

    try:
        query_embedding = generate_embedding(question)
        review_context = search_review_embeddings(query_embedding, provider_ids)
        review_context = enrich_review_context_with_provider_info(review_context, db)

        if not has_review_context(review_context):
            review_context_source = "sqlite"
            review_context = build_provider_review_context(provider_ids, db)
    except Exception:
        review_context_source = "sqlite"
        review_context = build_provider_review_context(provider_ids, db)

    return {
        "answer": "I found relevant review data.",
        "review_context_source": review_context_source,
        "review_context": review_context,
    }


def format_booking_status_history(history: models.BookingStatusHistory):
    return {
        "id": history.id,
        "booking_id": history.booking_id,
        "changed_by_user_id": history.changed_by_user_id,
        "old_status": history.old_status,
        "new_status": history.new_status,
        "note": history.note,
        "changed_at": history.changed_at,
    }


def format_payment_for_ai_tool(payment: models.Payment):
    return {
        "id": payment.id,
        "booking_id": payment.booking_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "status": payment.status,
        "payment_method": payment.payment_method,
        "created_at": payment.created_at,
        "paid_at": payment.paid_at,
        "refunded_at": payment.refunded_at,
    }


def format_refund_request_for_ai_tool(refund_request: models.RefundRequest):
    return {
        "id": refund_request.id,
        "booking_id": refund_request.booking_id,
        "payment_id": refund_request.payment_id,
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
    }


def get_booking_status_tool(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    histories = (
        db.query(models.BookingStatusHistory)
        .filter(models.BookingStatusHistory.booking_id == booking.id)
        .order_by(models.BookingStatusHistory.id.desc())
        .limit(5)
        .all()
    )
    payments = (
        db.query(models.Payment)
        .filter(models.Payment.booking_id == booking.id)
        .order_by(models.Payment.id.desc())
        .all()
    )
    refund_requests = (
        db.query(models.RefundRequest)
        .filter(models.RefundRequest.booking_id == booking.id)
        .order_by(models.RefundRequest.id.desc())
        .all()
    )
    status = booking.status

    return {
        "booking": format_booking_detail_response(booking, db),
        "status_explanation": BOOKING_STATUS_EXPLANATIONS.get(status),
        "recent_status_histories": [
            format_booking_status_history(history) for history in histories
        ],
        "payments": [format_payment_for_ai_tool(payment) for payment in payments],
        "refund_requests": [
            format_refund_request_for_ai_tool(refund_request)
            for refund_request in refund_requests
        ],
    }


def explain_booking_flow_tool(topic: str | None = None):
    normalized_topic = topic.strip().lower() if topic else None
    topic_status_map = {
        "pending": ["pending"],
        "quoted": ["quoted"],
        "quote": ["quoted"],
        "payment": ["quoted", "accepted"],
        "pay": ["quoted", "accepted"],
        "complete": ["accepted", "awaiting_confirmation", "completed"],
        "refund": [
            "completed",
            "refunding",
            "refunded",
        ],
        "complaint": ["accepted", "awaiting_confirmation", "completed"],
        "cancel": ["pending", "quoted", "cancelled"],
        "reject": ["pending", "quoted", "rejected"],
    }
    selected_statuses = None
    if normalized_topic:
        selected_statuses = topic_status_map.get(normalized_topic)

    if not selected_statuses:
        selected_statuses = list(BOOKING_STATUS_EXPLANATIONS.keys())

    return {
        "topic": topic,
        "flow_steps": BOOKING_FLOW_STEPS,
        "statuses": {
            status: BOOKING_STATUS_EXPLANATIONS[status]
            for status in selected_statuses
            if status in BOOKING_STATUS_EXPLANATIONS
        },
    }


def build_pending_ai_action(
    action_type: str,
    summary: str,
    payload: dict,
    current_user: models.User,
    db: Session,
    warnings: list[str] | None = None,
):
    action = create_ai_pending_action(
        current_user.id,
        action_type,
        payload,
        summary,
        warnings,
        db,
    )
    action["confirmation_required"] = True

    return action


def ensure_current_user_is_customer(current_user: models.User):
    if current_user.role != "customer":
        raise HTTPException(
            status_code=403, detail="Only customers can use this action"
        )


def ensure_current_user_is_provider(current_user: models.User):
    if current_user.role != "provider":
        raise HTTPException(
            status_code=403, detail="Only providers can use this action"
        )


def get_provider_booking_for_ai_action(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    ensure_current_user_is_provider(current_user)
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    booking = (
        db.query(models.Booking)
        .filter(
            models.Booking.id == booking_id,
            models.Booking.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    return booking


def get_provider_refund_request_for_ai_action(
    refund_request_id: int,
    current_user: models.User,
    db: Session,
):
    ensure_current_user_is_provider(current_user)
    provider_profile = get_provider_profile_for_user(current_user.id, db)
    refund_request = (
        db.query(models.RefundRequest)
        .filter(
            models.RefundRequest.id == refund_request_id,
            models.RefundRequest.provider_profile_id == provider_profile.id,
        )
        .first()
    )
    if not refund_request:
        raise HTTPException(status_code=404, detail="Refund request not found")

    return refund_request


def prepare_create_booking_action_tool(
    provider_profile_id: int,
    service_description: str,
    service_address: str,
    service_latitude: float,
    service_longitude: float,
    scheduled_start_time,
    scheduled_end_time,
    current_user: models.User,
    db: Session,
    chat_room_id: int | None = None,
):
    ensure_current_user_is_customer(current_user)
    booking_data = BookingCreate(
        provider_profile_id=provider_profile_id,
        chat_room_id=chat_room_id,
        title=" ".join(service_description.split()[:30]),
        service_description=service_description,
        service_address=service_address,
        service_latitude=service_latitude,
        service_longitude=service_longitude,
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
    )
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking_data.provider_profile_id)
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    require_provider_can_accept_orders(provider_profile, db)

    ensure_provider_available_for_datetime_range(
        provider_profile.id,
        booking_data.scheduled_start_time,
        booking_data.scheduled_end_time,
        db,
    )

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

    payload = {
        "provider_profile_id": booking_data.provider_profile_id,
        "chat_room_id": booking_data.chat_room_id,
        "title": booking_data.title,
        "service_description": booking_data.service_description,
        "service_address": booking_data.service_address,
        "service_latitude": booking_data.service_latitude,
        "service_longitude": booking_data.service_longitude,
        "scheduled_start_time": booking_data.scheduled_start_time.isoformat(),
        "scheduled_end_time": booking_data.scheduled_end_time.isoformat(),
    }

    return build_pending_ai_action(
        "create_booking",
        "On confirm, creates a booking request and opens or reuses a chat room with the provider.",
        payload,
        current_user,
        db,
        ["AI booking creation does not include attachments; use the standard booking API for images or video."],
    )


BOOKING_DRAFT_FIELD_CONFIG = {
    "provider_profile_id": {
        "label": "Provider",
        "type": "integer",
        "question": "Which provider would you like to book? Reply with a list number or provider profile id.",
    },
    "service_description": {
        "label": "Service description",
        "type": "string",
        "question": "Describe the service needed, e.g. elderly daily care, escort to appointment, meal assistance.",
    },
    "service_address": {
        "label": "Service address",
        "type": "string",
        "question": "Please provide the service address; the app can also fill this from location.",
    },
    "service_latitude": {
        "label": "Service latitude",
        "type": "number",
        "question": "Service latitude is still needed; the app can send it from location.",
    },
    "service_longitude": {
        "label": "Service longitude",
        "type": "number",
        "question": "Service longitude is still needed; the app can send it from location.",
    },
    "scheduled_start_time": {
        "label": "Start time",
        "type": "datetime",
        "question": "When should the service start? Please give a specific time.",
    },
    "scheduled_end_time": {
        "label": "End time",
        "type": "datetime",
        "question": "When should the service end? Please give a specific time.",
    },
}

BOOKING_DRAFT_REQUIRED_FIELDS = list(BOOKING_DRAFT_FIELD_CONFIG.keys())


def is_missing_booking_draft_value(value):
    return value is None or (isinstance(value, str) and not value.strip())


def merge_booking_draft_fields(existing_draft: dict | None, new_fields: dict):
    draft = {}

    if existing_draft:
        draft.update(existing_draft.get("provided_fields") or existing_draft)

    for key, value in new_fields.items():
        if not is_missing_booking_draft_value(value):
            draft[key] = value

    return draft


def format_booking_draft_missing_field(field_name: str):
    config = BOOKING_DRAFT_FIELD_CONFIG[field_name]

    return {
        "name": field_name,
        "label": config["label"],
        "type": config["type"],
        "question": config["question"],
    }


def format_booking_draft_provider_preview(provider_profile_id: int | None, db: Session):
    if provider_profile_id is None:
        return None

    provider = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == provider_profile_id)
        .first()
    )

    return format_provider_preview(provider)


def build_booking_draft_preview(
    draft: dict, missing_field_names: list[str], db: Session
):
    fields = []
    field_labels = {
        field_name: config["label"]
        for field_name, config in BOOKING_DRAFT_FIELD_CONFIG.items()
    }

    for field_name in BOOKING_DRAFT_REQUIRED_FIELDS:
        value = draft.get(field_name)
        fields.append(
            {
                "name": field_name,
                "label": field_labels[field_name],
                "value": value,
                "filled": not is_missing_booking_draft_value(value),
                "missing": field_name in missing_field_names,
            }
        )

    return {
        "ui_type": "booking_draft_preview",
        "title": "Booking draft",
        "draft_type": "create_booking",
        "provider": format_booking_draft_provider_preview(
            draft.get("provider_profile_id"),
            db,
        ),
        "fields": fields,
        "missing_field_names": missing_field_names,
        "ready_to_confirm": len(missing_field_names) == 0,
    }


def build_booking_draft_missing_info_response(
    draft: dict,
    missing_field_names: list[str],
    db: Session,
    provider_choices: list[dict] | None = None,
):
    next_field_name = missing_field_names[0]

    return {
        "draft_status": "missing_info",
        "draft_type": "create_booking",
        "provided_fields": draft,
        "missing_field_names": missing_field_names,
        "missing_fields": [
            format_booking_draft_missing_field(field_name)
            for field_name in missing_field_names
        ],
        "provider_choices": provider_choices or [],
        "preview": build_booking_draft_preview(draft, missing_field_names, db),
        "next_question": BOOKING_DRAFT_FIELD_CONFIG[next_field_name]["question"],
    }


def normalize_booking_draft_datetime(value):
    if isinstance(value, str):
        return datetime.fromisoformat(value)

    return value


def prepare_booking_draft_action_tool(
    current_user: models.User,
    db: Session,
    provider_profile_id: int | None = None,
    service_description: str | None = None,
    service_address: str | None = None,
    service_latitude: float | None = None,
    service_longitude: float | None = None,
    scheduled_start_time=None,
    scheduled_end_time=None,
    chat_room_id: int | None = None,
    existing_draft: dict | None = None,
    provider_choices: list[dict] | None = None,
):
    ensure_current_user_is_customer(current_user)
    draft = merge_booking_draft_fields(
        existing_draft,
        {
            "provider_profile_id": provider_profile_id,
            "chat_room_id": chat_room_id,
            "service_description": service_description,
            "service_address": service_address,
            "service_latitude": service_latitude,
            "service_longitude": service_longitude,
            "scheduled_start_time": scheduled_start_time,
            "scheduled_end_time": scheduled_end_time,
        },
    )
    missing_field_names = [
        field_name
        for field_name in BOOKING_DRAFT_REQUIRED_FIELDS
        if is_missing_booking_draft_value(draft.get(field_name))
    ]

    if missing_field_names:
        return build_booking_draft_missing_info_response(
            draft,
            missing_field_names,
            db,
            provider_choices,
        )

    return prepare_create_booking_action_tool(
        provider_profile_id=draft["provider_profile_id"],
        chat_room_id=draft.get("chat_room_id"),
        service_description=draft["service_description"],
        service_address=draft["service_address"],
        service_latitude=draft["service_latitude"],
        service_longitude=draft["service_longitude"],
        scheduled_start_time=normalize_booking_draft_datetime(
            draft["scheduled_start_time"]
        ),
        scheduled_end_time=normalize_booking_draft_datetime(
            draft["scheduled_end_time"]
        ),
        current_user=current_user,
        db=db,
    )


def prepare_cancel_booking_action_tool(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    ensure_current_user_is_customer(current_user)
    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    if booking.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only cancel your booking")

    ensure_booking_status(
        booking,
        [BookingStatus.pending, BookingStatus.quoted, BookingStatus.awaiting_payment],
        "Only pending, quoted or awaiting payment bookings can be cancelled",
    )

    return build_pending_ai_action(
        "cancel_booking",
        f"On confirm, booking {booking.id} will be cancelled.",
        {
            "booking_id": booking.id,
        },
        current_user,
        db,
    )


def prepare_refund_request_action_tool(
    booking_id: int,
    reason: str,
    current_user: models.User,
    db: Session,
):
    ensure_current_user_is_customer(current_user)
    if not reason.strip():
        raise HTTPException(status_code=400, detail="Refund reason cannot be empty")

    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    if booking.customer_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You can only request refunds for your booking"
        )

    ensure_booking_status(
        booking,
        [BookingStatus.completed],
        "Only completed bookings can request a refund",
    )
    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.booking_id == booking.id,
            models.Payment.customer_id == current_user.id,
            models.Payment.status == PaymentStatus.paid,
        )
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=400, detail="Paid payment not found for this booking"
        )

    if db.query(models.RefundRequest).filter(models.RefundRequest.payment_id == payment.id).first():
        raise HTTPException(
            status_code=400, detail="This payment already has a refund request"
        )

    return build_pending_ai_action(
        "request_refund",
        f"On confirm, a refund request will be created for booking {booking.id} and the provider will be notified.",
        {
            "booking_id": booking.id,
            "reason": reason.strip(),
        },
        current_user,
        db,
    )


def prepare_pay_booking_action_tool(
    booking_id: int,
    current_user: models.User,
    db: Session,
    payment_method: str = "iyzico_checkout",
):
    ensure_current_user_is_customer(current_user)
    if not payment_method.strip():
        raise HTTPException(status_code=400, detail="Payment method cannot be empty")

    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    if booking.customer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only pay your booking")

    ensure_booking_status(
        booking,
        [BookingStatus.awaiting_payment],
        "Only awaiting payment bookings can be paid",
    )
    if booking.quote_amount is None:
        raise HTTPException(status_code=400, detail="Booking has no quote amount")

    pending_payment = (
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
        .first()
    )
    if not pending_payment:
        raise HTTPException(
            status_code=400,
            detail="Pending payment not found for this booking",
        )

    return build_pending_ai_action(
        "pay_booking",
        f"On confirm, quote {booking.quote_amount} TRY for booking {booking.id} will be paid and work will begin.",
        {
            "booking_id": booking.id,
            "payment_method": payment_method.strip(),
        },
        current_user,
        db,
    )


def prepare_reject_quote_action_tool(
    booking_id: int,
    status_note: str,
    current_user: models.User,
    db: Session,
):
    ensure_current_user_is_customer(current_user)
    if not status_note.strip():
        raise HTTPException(status_code=400, detail="Status note cannot be empty")

    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    if booking.customer_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You can only reject quotes for your booking"
        )

    ensure_booking_status(
        booking, [BookingStatus.quoted], "Only quoted bookings can reject a quote"
    )

    return build_pending_ai_action(
        "reject_quote",
        f"On confirm, the quote for booking {booking.id} will be rejected and it returns to pending.",
        {
            "booking_id": booking.id,
            "status_note": status_note.strip(),
        },
        current_user,
        db,
    )


def prepare_confirm_complete_action_tool(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    ensure_current_user_is_customer(current_user)
    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    if booking.customer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only confirm completion for your booking",
        )

    ensure_booking_status(
        booking,
        [BookingStatus.awaiting_confirmation],
        "Only bookings waiting for confirmation can be completed",
    )

    return build_pending_ai_action(
        "confirm_complete",
        f"On confirm, booking {booking.id} will be accepted and marked completed.",
        {
            "booking_id": booking.id,
        },
        current_user,
        db,
    )


def prepare_reject_complete_action_tool(
    booking_id: int,
    status_note: str,
    current_user: models.User,
    db: Session,
):
    ensure_current_user_is_customer(current_user)
    if not status_note.strip():
        raise HTTPException(status_code=400, detail="Status note cannot be empty")

    booking = get_booking_for_user_or_404(booking_id, current_user, db)
    if booking.customer_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only reject completion for your booking",
        )

    ensure_booking_status(
        booking,
        [BookingStatus.awaiting_confirmation],
        "Only bookings waiting for confirmation can be rejected",
    )

    return build_pending_ai_action(
        "reject_complete",
        f"On confirm, completion for booking {booking.id} will be rejected and it returns to accepted.",
        {
            "booking_id": booking.id,
            "status_note": status_note.strip(),
        },
        current_user,
        db,
    )


def prepare_quote_booking_action_tool(
    booking_id: int,
    quote_amount: float,
    visit_fee_amount: float,
    current_user: models.User,
    db: Session,
    quote_message: str | None = None,
):
    quote_data = ProviderBookingQuoteCreate(
        quote_amount=quote_amount,
        expected_service_amount=quote_amount,
        visit_fee_amount=visit_fee_amount,
        quote_message=quote_message,
    )
    booking = get_provider_booking_for_ai_action(booking_id, current_user, db)
    ensure_booking_status(
        booking,
        [BookingStatus.pending],
        "Only pending bookings can receive a quote",
    )

    return build_pending_ai_action(
        "quote_booking",
        f"On confirm, booking {booking.id} will have an expected service amount of {quote_data.quote_amount} TRY and a visit fee of {quote_data.visit_fee_amount} TRY; the customer will be notified.",
        {
            "booking_id": booking.id,
            "quote_amount": quote_data.quote_amount,
            "expected_service_amount": quote_data.expected_service_amount,
            "visit_fee_amount": quote_data.visit_fee_amount,
            "quote_message": quote_data.quote_message,
        },
        current_user,
        db,
    )


def prepare_reject_booking_action_tool(
    booking_id: int,
    status_note: str,
    current_user: models.User,
    db: Session,
):
    note_data = BookingNoteUpdate(status_note=status_note)
    booking = get_provider_booking_for_ai_action(booking_id, current_user, db)
    ensure_booking_status(
        booking,
        [BookingStatus.pending],
        "Only pending bookings can be rejected",
    )

    return build_pending_ai_action(
        "reject_booking",
        f"On confirm, booking {booking.id} will be rejected and the reason sent to the customer.",
        {
            "booking_id": booking.id,
            "status_note": note_data.status_note,
        },
        current_user,
        db,
    )


def prepare_complete_booking_action_tool(
    booking_id: int,
    current_user: models.User,
    db: Session,
):
    booking = get_provider_booking_for_ai_action(booking_id, current_user, db)
    ensure_booking_status(
        booking,
        [BookingStatus.accepted],
        "Only accepted bookings can be completed",
    )

    return build_pending_ai_action(
        "complete_booking",
        f"On confirm, booking {booking.id} will be marked complete pending customer acceptance.",
        {
            "booking_id": booking.id,
        },
        current_user,
        db,
    )


def prepare_approve_refund_action_tool(
    refund_request_id: int,
    current_user: models.User,
    db: Session,
):
    refund_request = get_provider_refund_request_for_ai_action(
        refund_request_id,
        current_user,
        db,
    )
    if refund_request.status != RefundRequestStatus.pending:
        raise HTTPException(
            status_code=400, detail="Only pending refund requests can be approved"
        )

    booking = get_provider_booking_for_ai_action(
        refund_request.booking_id,
        current_user,
        db,
    )
    ensure_booking_status(
        booking,
        [BookingStatus.refunding],
        "Only refunding bookings can be refunded",
    )

    return build_pending_ai_action(
        "approve_refund",
        f"On confirm, refund request {refund_request.id} will be approved and booking {booking.id} becomes refunded.",
        {
            "refund_request_id": refund_request.id,
        },
        current_user,
        db,
    )


def prepare_reject_refund_action_tool(
    refund_request_id: int,
    provider_note: str,
    current_user: models.User,
    db: Session,
):
    reject_data = ProviderRefundRejectCreate(provider_note=provider_note)
    refund_request = get_provider_refund_request_for_ai_action(
        refund_request_id,
        current_user,
        db,
    )
    if refund_request.status != RefundRequestStatus.pending:
        raise HTTPException(
            status_code=400, detail="Only pending refund requests can be rejected"
        )

    booking = get_provider_booking_for_ai_action(
        refund_request.booking_id,
        current_user,
        db,
    )
    ensure_booking_status(
        booking,
        [BookingStatus.refunding],
        "Only refunding bookings can keep a rejected refund request",
    )

    return build_pending_ai_action(
        "reject_refund",
        f"On confirm, refund request {refund_request.id} will be rejected and booking {booking.id} stays refunding.",
        {
            "refund_request_id": refund_request.id,
            "provider_note": reject_data.provider_note,
        },
        current_user,
        db,
    )


def create_chat_room_tool(
    provider_profile_id: int,
    current_user: models.User,
    db: Session,
):
    if current_user.role != "customer":
        raise HTTPException(
            status_code=403,
            detail="Only customers can start chats with providers",
        )

    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == provider_profile_id)
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider profile not found")

    if provider_profile.user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot open a chat with yourself",
        )

    if provider_profile.verification_status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Only approved providers can receive chats",
        )

    existing_chat_room = (
        db.query(models.ChatRoom)
        .filter(
            models.ChatRoom.customer_id == current_user.id,
            models.ChatRoom.provider_profile_id == provider_profile_id,
        )
        .first()
    )
    if existing_chat_room:
        return {
            "message": "Chat room already exists",
            "created": False,
            "chat_room": format_chat_room_response_with_unread(
                existing_chat_room,
                db,
                current_user,
            ),
        }

    chat_room = get_or_create_chat_room(
        customer_id=current_user.id,
        provider_profile_id=provider_profile_id,
        db=db,
    )
    db.commit()
    db.refresh(chat_room)

    create_notification(
        provider_profile.user_id,
        "New chat started",
        "A customer started a chat with you",
        NotificationType.chat_started,
        NotificationRelatedType.chat_room,
        chat_room.id,
        db,
    )
    db.commit()

    return {
        "message": "Chat room created successfully",
        "created": True,
        "chat_room": format_chat_room_response_with_unread(
            chat_room,
            db,
            current_user,
        ),
    }
