import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend import models
from backend.core.clock import utc_now


def build_ai_chat_request_metadata(request_data):
    return {
        "service_province": request_data.service_province,
        "service_address": request_data.service_address,
        "max_price": request_data.max_price,
        "latitude": request_data.latitude,
        "longitude": request_data.longitude,
        "max_distance_km": request_data.max_distance_km,
        "scheduled_start_time": (
            request_data.scheduled_start_time.isoformat()
            if request_data.scheduled_start_time
            else None
        ),
        "scheduled_end_time": (
            request_data.scheduled_end_time.isoformat()
            if request_data.scheduled_end_time
            else None
        ),
        "candidate_provider_ids": request_data.candidate_provider_ids,
    }


def build_provider_recommendation_snapshot(recommendations: list[dict]):
    snapshots = []

    for recommendation in recommendations:
        stats = recommendation.get("stats") or {}
        snapshots.append(
            {
                "provider_id": recommendation.get("provider_id"),
                "business_name": recommendation.get("business_name"),
                "service_province": recommendation.get("service_province"),
                "tags": recommendation.get("tags"),
                "hourly_rate": recommendation.get("hourly_rate"),
                "distance_km": recommendation.get("distance_km"),
                "is_available_for_requested_time": recommendation.get(
                    "is_available_for_requested_time"
                ),
                "match_score": recommendation.get("match_score"),
                "reason": recommendation.get("reason"),
                "average_rating": stats.get("average_rating"),
                "review_count": stats.get("review_count"),
                "completed_bookings": stats.get("completed_bookings"),
            }
        )

    return snapshots


def save_ai_chat_message(
    user_id: int,
    role: str,
    message: str,
    db: Session,
    intent: str | None = None,
    response_type: str | None = None,
    metadata: dict | None = None,
):
    ai_chat_message = models.AIChatMessage(
        user_id=user_id,
        role=role,
        message=message,
        intent=intent,
        response_type=response_type,
        metadata_json=(
            json.dumps(metadata, ensure_ascii=False) if metadata is not None else None
        ),
        created_at=utc_now(),
    )

    db.add(ai_chat_message)
    db.commit()
    db.refresh(ai_chat_message)

    return ai_chat_message


def save_ai_chat_exchange(
    user_id: int,
    user_message: str,
    assistant_message: str,
    intent: str,
    response_type: str,
    user_metadata: dict | None,
    assistant_metadata: dict | None,
    db: Session,
):
    save_ai_chat_message(
        user_id=user_id,
        role="user",
        message=user_message,
        intent=intent,
        response_type=response_type,
        metadata=user_metadata,
        db=db,
    )
    save_ai_chat_message(
        user_id=user_id,
        role="assistant",
        message=assistant_message,
        intent=intent,
        response_type=response_type,
        metadata=assistant_metadata,
        db=db,
    )


def get_recent_ai_chat_history(
    user_id: int,
    db: Session,
    limit: int = 10,
):
    messages = (
        db.query(models.AIChatMessage)
        .filter(models.AIChatMessage.user_id == user_id)
        .order_by(models.AIChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    messages.reverse()

    return [
        {
            "role": message.role,
            "content": message.message,
        }
        for message in messages
        if message.role in ["user", "assistant"]
    ]


def get_last_recommended_provider_ids_from_history(
    user_id: int,
    db: Session,
):
    messages = (
        db.query(models.AIChatMessage)
        .filter(
            models.AIChatMessage.user_id == user_id,
            models.AIChatMessage.role == "assistant",
            models.AIChatMessage.response_type == "provider_search",
        )
        .order_by(models.AIChatMessage.created_at.desc())
        .all()
    )

    for message in messages:
        if not message.metadata_json:
            continue

        try:
            metadata = json.loads(message.metadata_json)
        except json.JSONDecodeError:
            continue

        provider_ids = metadata.get("recommended_provider_ids")

        if provider_ids:
            return provider_ids

        recommended_providers = metadata.get("recommended_providers") or []
        provider_ids = [
            provider.get("provider_id")
            for provider in recommended_providers
            if provider.get("provider_id")
        ]

        if provider_ids:
            return provider_ids

    return []


def get_last_provider_recommendation_context_from_history(
    user_id: int,
    db: Session,
):
    messages = (
        db.query(models.AIChatMessage)
        .filter(
            models.AIChatMessage.user_id == user_id,
            models.AIChatMessage.role == "assistant",
            models.AIChatMessage.response_type == "provider_search",
        )
        .order_by(models.AIChatMessage.created_at.desc())
        .all()
    )

    for message in messages:
        if not message.metadata_json:
            continue

        try:
            metadata = json.loads(message.metadata_json)
        except json.JSONDecodeError:
            continue

        recommended_providers = metadata.get("recommended_providers") or []
        if recommended_providers:
            return recommended_providers

    return []


def get_last_pending_clarification_from_history(
    user_id: int,
    db: Session,
):
    message = (
        db.query(models.AIChatMessage)
        .filter(
            models.AIChatMessage.user_id == user_id,
            models.AIChatMessage.role == "assistant",
        )
        .order_by(models.AIChatMessage.created_at.desc())
        .first()
    )

    if (
        not message
        or message.response_type != "tool_error"
        or not message.metadata_json
    ):
        return None

    try:
        metadata = json.loads(message.metadata_json)
    except json.JSONDecodeError:
        return None

    return metadata.get("pending_clarification")


def get_last_booking_draft_from_history(
    user_id: int,
    db: Session,
):
    messages = (
        db.query(models.AIChatMessage)
        .filter(
            models.AIChatMessage.user_id == user_id,
            models.AIChatMessage.role == "assistant",
        )
        .order_by(models.AIChatMessage.created_at.desc())
        .limit(20)
        .all()
    )

    for message in messages:
        if not message.metadata_json:
            continue

        try:
            metadata = json.loads(message.metadata_json)
        except json.JSONDecodeError:
            continue

        if message.response_type == "booking_draft_cancelled":
            return None

        if message.response_type == "ai_action_confirmation":
            pending_action = metadata.get("pending_action") or {}
            if pending_action.get("action_type") == "create_booking":
                return None

        if message.response_type == "booking_draft_missing_info":
            return metadata.get("booking_draft")

    return None


def resolve_candidate_provider_ids(
    requested_provider_ids: list[int],
    recent_provider_ids: list[int],
    history_provider_ids: list[int],
):
    allowed_provider_ids = recent_provider_ids or history_provider_ids

    if not requested_provider_ids:
        return allowed_provider_ids

    return [
        provider_id
        for provider_id in requested_provider_ids
        if provider_id in allowed_provider_ids
    ]


def format_ai_chat_message(ai_chat_message: models.AIChatMessage):
    metadata = None

    if ai_chat_message.metadata_json:
        try:
            metadata = json.loads(ai_chat_message.metadata_json)
        except json.JSONDecodeError:
            metadata = None

    return {
        "id": ai_chat_message.id,
        "user_id": ai_chat_message.user_id,
        "role": ai_chat_message.role,
        "message": ai_chat_message.message,
        "intent": ai_chat_message.intent,
        "response_type": ai_chat_message.response_type,
        "metadata": metadata,
        "created_at": ai_chat_message.created_at,
    }


def delete_ai_chat_messages(user_id: int, db: Session):
    deleted_count = (
        db.query(models.AIChatMessage)
        .filter(models.AIChatMessage.user_id == user_id)
        .delete(synchronize_session=False)
    )
    db.commit()

    return deleted_count
