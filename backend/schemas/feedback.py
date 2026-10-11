from datetime import date, datetime, time
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from backend.constants import ALLOWED_PROVIDER_TAGS

from backend.schemas.auth import UserResponse
from backend.schemas.common import *  # noqa: F403

class ComplaintCreate(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Reason cannot be empty")

        return value

class ComplaintStatus(str, Enum):
    open = "open"
    resolved = "resolved"
    rejected = "rejected"

class AdminComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    admin_note: str

    @field_validator("admin_note")
    @classmethod
    def validate_admin_note_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Admin note cannot be empty")

        return value

class NotificationType(str, Enum):
    chat_started = "chat_started"
    chat_message_received = "chat_message_received"
    booking_created = "booking_created"
    booking_quoted = "booking_quoted"
    booking_quote_accepted = "booking_quote_accepted"
    booking_quote_rejected = "booking_quote_rejected"
    booking_rejected = "booking_rejected"
    booking_cancelled = "booking_cancelled"
    booking_completed_by_provider = "booking_completed_by_provider"
    booking_completion_confirmed = "booking_completion_confirmed"
    booking_completion_rejected = "booking_completion_rejected"
    booking_status_updated_by_admin = "booking_status_updated_by_admin"
    payment_paid = "payment_paid"
    refund_requested = "refund_requested"
    refund_approved = "refund_approved"
    refund_rejected = "refund_rejected"
    refund_appealed = "refund_appealed"
    refund_admin_approved = "refund_admin_approved"
    refund_admin_rejected = "refund_admin_rejected"
    refund_cancelled = "refund_cancelled"
    complaint_created = "complaint_created"
    complaint_resolved = "complaint_resolved"
    complaint_rejected = "complaint_rejected"
    complaint_reopened = "complaint_reopened"
    provider_profile_approved = "provider_profile_approved"
    provider_profile_rejected = "provider_profile_rejected"
    provider_portfolio_approved = "provider_portfolio_approved"
    provider_portfolio_rejected = "provider_portfolio_rejected"

class NotificationRelatedType(str, Enum):
    chat_room = "chat_room"
    booking = "booking"
    payment = "payment"
    refund_request = "refund_request"
    complaint = "complaint"
    provider_profile = "provider_profile"
    provider_portfolio = "provider_portfolio"

class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=1, max_length=1000)

class ReviewUpdate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None

class ReviewResponse(BaseModel):
    id: int
    booking_id: int
    customer_id: int
    provider_profile_id: int
    rating: int
    comment: str | None = None
    created_at: str | None = None
    is_visible: bool
    embedding_status: str | None = None
    embedding_error: str | None = None
    embedding_synced_at: str | None = None

class ReviewDetailResponse(ReviewResponse):
    customer: UserResponse | None = None

class RatingSummaryResponse(BaseModel):
    provider_profile_id: int
    average_rating: float | None = None
    review_count: int

class ReviewVisibilityUpdate(BaseModel):
    is_visible: bool

