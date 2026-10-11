"""AI pending action helpers.

AI cannot directly create bookings, payments, refunds, or change status; it creates `AIPendingAction` first.
The frontend shows preview/confirmation cards; routers execute real actions after user confirmation.
"""

import json
from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.schemas import AIPendingActionStatus
from backend.core.clock import parse_dt, utc_now
from backend.core.serialize import jsonable

AI_PENDING_ACTION_EXPIRE_MINUTES = 30


def dump_json(data: Any):
    return json.dumps(jsonable(data), ensure_ascii=False)


def load_json(data: str | None, default: Any = None):
    if not data:
        return default

    return json.loads(data)


def parse_iso_datetime(value):
    parsed = parse_dt(value)
    if parsed is None:
        raise ValueError("invalid datetime")
    return parsed


def format_provider_preview(provider: models.ProviderProfile | None):
    if not provider:
        return None

    return {
        "id": provider.id,
        "business_name": provider.business_name,
        "service_province": provider.service_province,
        "hourly_rate": provider.hourly_rate,
        "verification_status": provider.verification_status,
    }


def build_field(label: str, value: Any):
    return {
        "label": label,
        "value": value,
    }


def get_booking_preview_data(booking_id: int | None, db: Session):
    if booking_id is None:
        return None, None

    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        return None, None

    provider = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == booking.provider_profile_id)
        .first()
    )

    return booking, provider


def build_booking_fields(
    booking: models.Booking, provider: models.ProviderProfile | None
):
    return [
        build_field("Booking ID", booking.id),
        build_field("Provider", provider.business_name if provider else None),
        build_field("Service description", booking.service_description),
        build_field("Service address", booking.service_address),
        build_field("Start time", booking.scheduled_start_time),
        build_field("End time", booking.scheduled_end_time),
        build_field("Current status", booking.status),
    ]


def get_refund_request_preview_data(refund_request_id: int | None, db: Session):
    if refund_request_id is None:
        return None, None, None

    refund_request = (
        db.query(models.RefundRequest)
        .filter(models.RefundRequest.id == refund_request_id)
        .first()
    )
    if not refund_request:
        return None, None, None

    booking, provider = get_booking_preview_data(refund_request.booking_id, db)

    return refund_request, booking, provider


def build_refund_request_fields(
    refund_request: models.RefundRequest,
    booking: models.Booking | None,
    provider: models.ProviderProfile | None,
):
    fields = [
        build_field("Refund request ID", refund_request.id),
        build_field("Booking ID", refund_request.booking_id),
        build_field("Provider", provider.business_name if provider else None),
        build_field("Refund reason", refund_request.reason),
        build_field("Refund status", refund_request.status),
        build_field("Provider reply", refund_request.provider_note),
        build_field("Appeal reason", refund_request.appeal_reason),
        build_field("Admin reply", refund_request.admin_note),
    ]
    if booking:
        fields.extend(
            [
                build_field("Service description", booking.service_description),
                build_field("Service address", booking.service_address),
                build_field("Booking status", booking.status),
                build_field("Booking amount", booking.quote_amount),
            ]
        )

    return fields


def build_ai_pending_action_preview(
    action: models.AIPendingAction,
    payload: dict,
    db: Session | None = None,
):
    action_type = action.action_type
    preview = {
        "title": action.summary,
        "action_type": action_type,
        "confirm_label": "Confirm",
        "fields": [],
    }

    if action_type == "create_booking":
        provider = None
        if db is not None:
            provider = (
                db.query(models.ProviderProfile)
                .filter(models.ProviderProfile.id == payload.get("provider_profile_id"))
                .first()
            )

        preview.update(
            {
                "title": "Confirm create booking",
                "confirm_label": "Confirm send booking request",
                "provider": format_provider_preview(provider),
                "fields": [
                    build_field(
                        "Provider",
                        (
                            provider.business_name
                            if provider
                            else payload.get("provider_profile_id")
                        ),
                    ),
                    build_field("Service description", payload.get("service_description")),
                    build_field("Service address", payload.get("service_address")),
                    build_field("Start time", payload.get("scheduled_start_time")),
                    build_field("End time", payload.get("scheduled_end_time")),
                ],
            }
        )
        return preview

    if action_type in ["approve_refund", "reject_refund"]:
        refund_request = None
        booking = None
        provider = None
        if db is not None:
            refund_request, booking, provider = get_refund_request_preview_data(
                payload.get("refund_request_id"),
                db,
            )

        refund_action_config = {
            "approve_refund": {
                "title": "Confirm approve refund",
                "confirm_label": "Confirm approve refund",
            },
            "reject_refund": {
                "title": "Confirm reject refund",
                "confirm_label": "Confirm reject refund",
                "extra_fields": [build_field("Rejection reason", payload.get("provider_note"))],
            },
        }
        config = refund_action_config[action_type]
        preview.update(
            {
                "title": config["title"],
                "confirm_label": config["confirm_label"],
                "refund_request_id": payload.get("refund_request_id"),
                "booking_id": booking.id if booking else None,
                "provider": format_provider_preview(provider),
            }
        )
        if refund_request:
            preview["fields"] = build_refund_request_fields(
                refund_request,
                booking,
                provider,
            ) + config.get("extra_fields", [])
        else:
            preview["fields"] = [
                build_field("Refund request ID", payload.get("refund_request_id")),
                *config.get("extra_fields", []),
            ]
            preview["warning"] = "Refund request not found or unreadable; it will be re-validated on confirm."

        return preview

    booking = None
    provider = None
    if db is not None:
        booking, provider = get_booking_preview_data(payload.get("booking_id"), db)

    action_config = {
        "cancel_booking": {
            "title": "Confirm cancel booking",
            "confirm_label": "Confirm cancel booking",
        },
        "request_refund": {
            "title": "Confirm refund request",
            "confirm_label": "Confirm submit refund",
            "extra_fields": [build_field("Refund reason", payload.get("reason"))],
        },
        "pay_booking": {
            "title": "Confirm pay quote",
            "confirm_label": "Confirm pay quote",
            "extra_fields": [
                build_field(
                    "Payment method",
                    payload.get("payment_method", "iyzico_checkout"),
                )
            ],
        },
        "reject_quote": {
            "title": "Confirm reject quote",
            "confirm_label": "Confirm reject quote",
            "extra_fields": [build_field("Rejection reason", payload.get("status_note"))],
        },
        "confirm_complete": {
            "title": "Confirm service complete",
            "confirm_label": "Confirm acceptance",
        },
        "reject_complete": {
            "title": "Confirm reject completion",
            "confirm_label": "Confirm reject completion",
            "extra_fields": [build_field("Rejection reason", payload.get("status_note"))],
        },
        "quote_booking": {
            "title": "Confirm submit quote",
            "confirm_label": "Confirm submit quote",
            "extra_fields": [
                build_field("Quote amount", payload.get("quote_amount")),
                build_field("Quote message", payload.get("quote_message")),
            ],
        },
        "reject_booking": {
            "title": "Confirm reject booking",
            "confirm_label": "Confirm reject booking",
            "extra_fields": [build_field("Rejection reason", payload.get("status_note"))],
        },
        "complete_booking": {
            "title": "Confirm mark complete",
            "confirm_label": "Confirm mark complete",
        },
    }
    config = action_config.get(action_type, {})
    preview.update(
        {
            "title": config.get("title", action.summary),
            "confirm_label": config.get("confirm_label", "Confirm"),
            "booking_id": payload.get("booking_id"),
            "provider": format_provider_preview(provider),
        }
    )

    if booking:
        fields = build_booking_fields(booking, provider)
        if action_type == "pay_booking":
            fields.append(build_field("Quote amount", booking.quote_amount))
        preview["fields"] = fields + config.get("extra_fields", [])
    else:
        preview["fields"] = [
            build_field("Booking ID", payload.get("booking_id")),
            *config.get("extra_fields", []),
        ]
        preview["warning"] = "Booking not found or unreadable; it will be re-validated on confirm."

    return preview


def format_ai_pending_action(
    action: models.AIPendingAction,
    db: Session | None = None,
):
    payload = load_json(action.payload_json, {})

    return {
        "id": action.id,
        "user_id": action.user_id,
        "action_type": action.action_type,
        "payload": payload,
        "summary": action.summary,
        "warnings": load_json(action.warnings_json, []),
        "preview": build_ai_pending_action_preview(action, payload, db),
        "status": action.status,
        "created_at": action.created_at,
        "expires_at": action.expires_at,
        "executed_at": action.executed_at,
        "confirm_endpoint": "/ai/actions/confirm",
        "cancel_endpoint": f"/ai/actions/{action.id}/cancel",
    }


def create_ai_pending_action(
    user_id: int,
    action_type: str,
    payload: dict,
    summary: str,
    warnings: list[str] | None,
    db: Session,
):
    now = utc_now()
    action = models.AIPendingAction(
        user_id=user_id,
        action_type=action_type,
        payload_json=dump_json(payload),
        summary=summary,
        warnings_json=dump_json(warnings or []),
        status=AIPendingActionStatus.pending,
        created_at=now,
        expires_at=now + timedelta(minutes=AI_PENDING_ACTION_EXPIRE_MINUTES),
        executed_at=None,
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    return format_ai_pending_action(action, db)


def get_ai_pending_action_or_404(
    action_id: int,
    current_user: models.User,
    db: Session,
):
    action = (
        db.query(models.AIPendingAction)
        .filter(
            models.AIPendingAction.id == action_id,
            models.AIPendingAction.user_id == current_user.id,
        )
        .first()
    )

    if not action:
        raise HTTPException(status_code=404, detail="AI pending action not found")

    return action


def is_ai_pending_action_expired(action: models.AIPendingAction):
    return parse_iso_datetime(action.expires_at) <= utc_now()


def refresh_ai_pending_action_expiration(
    action: models.AIPendingAction,
    db: Session,
):
    if action.status == AIPendingActionStatus.pending and is_ai_pending_action_expired(
        action
    ):
        action.status = AIPendingActionStatus.expired
        db.commit()
        db.refresh(action)

    return action


def expire_user_pending_actions(user_id: int, db: Session):
    actions = (
        db.query(models.AIPendingAction)
        .filter(
            models.AIPendingAction.user_id == user_id,
            models.AIPendingAction.status == AIPendingActionStatus.pending,
        )
        .all()
    )
    expired_count = 0

    for action in actions:
        if is_ai_pending_action_expired(action):
            action.status = AIPendingActionStatus.expired
            expired_count += 1

    if expired_count:
        db.commit()

    return expired_count


def get_confirmable_ai_pending_action(
    action_id: int,
    current_user: models.User,
    db: Session,
):
    action = get_ai_pending_action_or_404(action_id, current_user, db)
    action = refresh_ai_pending_action_expiration(action, db)

    if action.status != AIPendingActionStatus.pending:
        raise HTTPException(
            status_code=400,
            detail="AI pending action is not pending",
        )

    return action


def cancel_ai_pending_action(
    action_id: int,
    current_user: models.User,
    db: Session,
):
    action = get_ai_pending_action_or_404(action_id, current_user, db)
    action = refresh_ai_pending_action_expiration(action, db)

    if action.status != AIPendingActionStatus.pending:
        raise HTTPException(
            status_code=400,
            detail="Only pending AI actions can be cancelled",
        )

    action.status = AIPendingActionStatus.cancelled
    db.commit()
    db.refresh(action)

    return format_ai_pending_action(action, db)


def mark_ai_pending_action_executed(
    action: models.AIPendingAction,
    db: Session,
):
    action.status = AIPendingActionStatus.executed
    action.executed_at = utc_now()
    db.commit()
    db.refresh(action)

    return format_ai_pending_action(action, db)
