from datetime import date, datetime, time
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

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
from backend.schemas.chat import ChatMessageResponse, ChatRoomResponse
from backend.schemas.common import *  # noqa: F403
from backend.schemas.provider import ProviderProfileResponse
from backend.core.clock import to_workshop_datetime

class BookingAttachmentResponse(BaseModel):
    id: int
    booking_id: int
    uploaded_by_user_id: int
    quote_revision_id: int | None = None
    purpose: Literal[
        "customer_attachment",
        "quote_attachment",
        "arrival_evidence",
        "completion_proof",
    ]
    original_file_name: str
    file_name: str
    file_url: str
    content_type: str
    size: int
    created_at: str

class BookingCreate(BaseModel):
    provider_profile_id: int
    chat_room_id: int | None = None
    title: str
    service_category: str
    service_description: str
    service_address: str
    service_latitude: float = Field(ge=-90, le=90)
    service_longitude: float = Field(ge=-180, le=180)
    customer_current_address: str | None = None
    customer_current_latitude: float | None = Field(default=None, ge=-90, le=90)
    customer_current_longitude: float | None = Field(default=None, ge=-180, le=180)
    scheduled_start_time: datetime
    scheduled_end_time: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "provider_profile_id": 1,
                "chat_room_id": 1,
                "service_description": "Kitchen pipe leak, needs on-site repair",
                "service_address": "Sultanahmet, Istanbul",
                "service_latitude": 41.0082,
                "service_longitude": 28.9784,
                "customer_current_address": "Taksim, Istanbul",
                "customer_current_latitude": 41.0369,
                "customer_current_longitude": 28.985,
                "scheduled_start_time": "2026-09-03T10:00:00",
                "scheduled_end_time": "2026-09-03T12:00:00",
            }
        }
    }

    @field_validator("service_category", "service_description", "service_address")
    @classmethod
    def validate_text_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Field cannot be empty")

        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        if len(value.split()) > 30:
            raise ValueError("Title must contain at most 30 words")
        return value

    @model_validator(mode="after")
    def validate_time_range(self):
        start = to_workshop_datetime(self.scheduled_start_time)
        end = to_workshop_datetime(self.scheduled_end_time)
        if end <= start:
            raise ValueError("Scheduled end time must be after scheduled start time")

        return self

class BookingUpdate(BaseModel):
    title: str
    service_description: str
    service_address: str
    service_latitude: float = Field(ge=-90, le=90)
    service_longitude: float = Field(ge=-180, le=180)
    customer_current_address: str | None = None
    customer_current_latitude: float | None = Field(default=None, ge=-90, le=90)
    customer_current_longitude: float | None = Field(default=None, ge=-180, le=180)
    scheduled_start_time: datetime
    scheduled_end_time: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "service_description": "Kitchen pipe leak, needs on-site repair",
                "service_address": "Sultanahmet, Istanbul",
                "service_latitude": 41.0082,
                "service_longitude": 28.9784,
                "customer_current_address": "Taksim, Istanbul",
                "customer_current_latitude": 41.0369,
                "customer_current_longitude": 28.985,
                "scheduled_start_time": "2026-09-03T10:00:00",
                "scheduled_end_time": "2026-09-03T12:00:00",
            }
        }
    }

    @field_validator("service_description", "service_address")
    @classmethod
    def validate_text_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Field cannot be empty")

        return value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        if len(value.split()) > 30:
            raise ValueError("Title must contain at most 30 words")
        return value

    @model_validator(mode="after")
    def validate_time_range(self):
        start = to_workshop_datetime(self.scheduled_start_time)
        end = to_workshop_datetime(self.scheduled_end_time)
        if end <= start:
            raise ValueError("Scheduled end time must be after scheduled start time")

        return self

class BookingStatus(str, Enum):
    pending = "pending"
    quoted = "quoted"
    awaiting_payment = "awaiting_payment"
    awaiting_visit_payment = "awaiting_visit_payment"
    visit_paid = "visit_paid"
    provider_arrived = "provider_arrived"
    awaiting_final_quote = "awaiting_final_quote"
    final_quote_sent = "final_quote_sent"
    awaiting_service_payment = "awaiting_service_payment"
    service_paid = "service_paid"
    accepted = "accepted"
    rejected = "rejected"
    refunding = "refunding"
    refunded = "refunded"
    partially_refunded = "partially_refunded"
    awaiting_confirmation = "awaiting_confirmation"
    completed = "completed"
    cancelled = "cancelled"
    cancelled_before_visit = "cancelled_before_visit"
    provider_no_show = "provider_no_show"
    visit_completed_closed = "visit_completed_closed"
    service_cancelled_after_payment = "service_cancelled_after_payment"

class BookingBaseResponse(BaseModel):
    id: int
    customer_id: int
    provider_profile_id: int
    chat_room_id: int | None = None
    title: str
    service_category: str | None = None
    service_description: str
    service_address: str
    service_latitude: float
    service_longitude: float
    customer_current_address: str | None = None
    customer_current_latitude: float | None = None
    customer_current_longitude: float | None = None
    booking_at: str
    scheduled_start_time: str
    scheduled_end_time: str
    completed_at: str | None = None
    total_amount: float
    quote_amount: float | None = None
    quote_message: str | None = None
    expected_service_amount: float | None = None
    visit_fee_amount: float | None = None
    final_quote_amount: float | None = None
    final_quote_message: str | None = None
    arrival_started_at: str | None = None
    final_quote_declined_at: str | None = None
    final_quote_decline_reason: str | None = None
    final_quote_confirmed_at: str | None = None
    closed_reason: str | None = None
    quoted_at: str | None = None
    status: BookingStatus
    status_note: str | None = None
    booking_notice: str | None = None

class BookingComplaintSummaryResponse(BaseModel):
    has_open_complaint: bool
    open_complaint_count: int
    total_complaint_count: int

class BookingDetailResponse(BookingBaseResponse):
    payment_method: str | None = None
    customer: UserResponse | None = None
    provider: ProviderProfileResponse | None = None
    attachments: list[BookingAttachmentResponse] = Field(default_factory=list)
    complaint_summary: BookingComplaintSummaryResponse
    current_refund_request: dict[str, Any] | None = None
    last_declined_quote: dict[str, Any] | None = None
    last_declined_final_quote: dict[str, Any] | None = None
    current_quote_revision_id: int | None = None

class ProviderBookingQuoteCreate(BaseModel):
    # quote_amount remains accepted for final-quote calls and old clients. For
    # an initial quote, expected_service_amount and visit_fee_amount are the
    # canonical fields.
    quote_amount: float | None = Field(default=None, gt=0)
    quote_message: str | None = None
    expected_service_amount: float | None = Field(default=None, gt=0)
    visit_fee_amount: float | None = Field(default=None, gt=0)

class BookingNoteUpdate(BaseModel):
    status_note: str

    @field_validator("status_note")
    @classmethod
    def validate_status_note_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Status note cannot be empty")

        return value

class AdminBookingStatusUpdate(BaseModel):
    status: BookingStatus
    status_note: str

    @field_validator("status_note")
    @classmethod
    def validate_status_note_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Status note cannot be empty")

        return value

class PaymentStatus(str, Enum):
    pending = "pending"
    checkout_created = "checkout_created"
    processing = "processing"
    authorized = "authorized"
    paid = "paid"
    voided = "voided"
    failed = "failed"
    capture_failed = "capture_failed"
    refunded = "refunded"
    partially_refunded = "partially_refunded"
    refund_failed = "refund_failed"


class PaymentStage(str, Enum):
    visit_fee = "visit_fee"
    service_fee = "service_fee"

class PaymentCreate(BaseModel):
    # Payment details are collected only by hosted checkout, never by this API.
    model_config = ConfigDict(extra="forbid")
    payment_method: str = "iyzico_checkout"
    payment_stage: PaymentStage = PaymentStage.visit_fee

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Payment method cannot be empty")

        return value

class RefundRequestStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    appealed = "appealed"
    admin_rejected = "admin_rejected"
    cancelled = "cancelled"

class RefundRequestCreate(BaseModel):
    reason: str
    refund_amount: float | None = Field(default=None, gt=0)

    @field_validator("reason")
    @classmethod
    def validate_reason_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Reason cannot be empty")

        return value

class RefundAppealCreate(BaseModel):
    appeal_reason: str

    @field_validator("appeal_reason")
    @classmethod
    def validate_appeal_reason_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Appeal reason cannot be empty")

        return value

class ProviderRefundRejectCreate(BaseModel):
    provider_note: str

    @field_validator("provider_note")
    @classmethod
    def validate_provider_note_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Provider note cannot be empty")

        return value

class AdminRefundDecisionCreate(BaseModel):
    admin_note: str

    @field_validator("admin_note")
    @classmethod
    def validate_admin_note_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Admin note cannot be empty")

        return value

class BookingCreateResponseData(BaseModel):
    booking: BookingDetailResponse
    chat_room: ChatRoomResponse
    chat_message: ChatMessageResponse

class BookingUpdateResponseData(BaseModel):
    message: str
    booking: BookingDetailResponse
    chat_message: ChatMessageResponse | None = None
