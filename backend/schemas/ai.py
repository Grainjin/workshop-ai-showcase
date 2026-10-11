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

from backend.schemas.common import *  # noqa: F403

class AIProviderRecommendRequest(BaseModel):
    query: str
    service_province: str | None = None
    service_location_id: int | None = Field(default=None, gt=0)
    max_price: float | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_distance_km: float | None = Field(default=None, gt=0)
    scheduled_start_time: datetime | None = None
    scheduled_end_time: datetime | None = None

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Query cannot be empty")

        return value

    @model_validator(mode="after")
    def validate_optional_pairs(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together")

        if (self.scheduled_start_time is None) != (self.scheduled_end_time is None):
            raise ValueError(
                "scheduled_start_time and scheduled_end_time must be provided together"
            )

        if (
            self.scheduled_start_time is not None
            and self.scheduled_end_time <= self.scheduled_start_time
        ):
            raise ValueError("scheduled_end_time must be after scheduled_start_time")

        return self

class AIChatRequest(BaseModel):
    message: str
    service_province: str | None = None
    service_location_id: int | None = Field(default=None, gt=0)
    service_address: str | None = None
    max_price: float | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    max_distance_km: float | None = Field(default=None, gt=0)
    scheduled_start_time: datetime | None = None
    scheduled_end_time: datetime | None = None
    candidate_provider_ids: list[int] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Message cannot be empty")

        return value

    @field_validator("service_province", "service_address")
    @classmethod
    def validate_optional_text_not_empty(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Field cannot be empty")

        return value

    @model_validator(mode="after")
    def validate_optional_pairs(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together")

        if (self.scheduled_start_time is None) != (self.scheduled_end_time is None):
            raise ValueError(
                "scheduled_start_time and scheduled_end_time must be provided together"
            )

        if (
            self.scheduled_start_time is not None
            and self.scheduled_end_time <= self.scheduled_start_time
        ):
            raise ValueError("scheduled_end_time must be after scheduled_start_time")

        return self

class AIIntentResponse(BaseModel):
    intent: str
    confidence: float
    reason: str | None = None

class AIToolCallResponse(BaseModel):
    name: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    selected_index: int | None = None

    model_config = ConfigDict(extra="allow")

class AIToolErrorData(BaseModel):
    tool_name: str | None = None
    tool_args: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    error_code: str | None = None
    error_type: str | None = None
    status_code: int | None = None
    error_details: Any = None

    model_config = ConfigDict(extra="allow")

class AIClarificationChoiceResponse(BaseModel):
    index: int
    booking_id: int | None = None
    refund_request_id: int | None = None
    service_description: str | None = None
    status: str | None = None
    scheduled_start_time: str | None = None
    booking: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")

class AIPendingClarificationResponse(BaseModel):
    tool_name: str
    target_field: str
    missing_fields: list[str] = Field(default_factory=list)
    original_tool_args: dict[str, Any] = Field(default_factory=dict)
    choices: list[AIClarificationChoiceResponse] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")

class AIConfirmationFieldResponse(BaseModel):
    label: str | None = None
    value: Any = None

    model_config = ConfigDict(extra="allow")

class AIConfirmationCardResponse(BaseModel):
    ui_type: str = "confirmation_card"
    action_id: int
    action_type: str
    title: str
    description: str | None = None
    status: str
    expires_at: str
    fields: list[AIConfirmationFieldResponse] = Field(default_factory=list)
    provider: dict[str, Any] | None = None
    booking_id: int | None = None
    refund_request_id: int | None = None
    warnings: list[str] = Field(default_factory=list)
    warning: str | None = None
    confirm_label: str = "Confirm"
    cancel_label: str = "Cancel"
    confirm_endpoint: str
    confirm_request: dict[str, Any]
    cancel_endpoint: str

    model_config = ConfigDict(extra="allow")

class AIBookingDraftMissingFieldResponse(BaseModel):
    name: str
    label: str
    type: str
    question: str

    model_config = ConfigDict(extra="allow")

class AIBookingDraftResponse(BaseModel):
    draft_status: str
    draft_type: str = "create_booking"
    provided_fields: dict[str, Any] = Field(default_factory=dict)
    missing_field_names: list[str] = Field(default_factory=list)
    missing_fields: list[AIBookingDraftMissingFieldResponse] = Field(
        default_factory=list
    )
    provider_choices: list[dict[str, Any]] = Field(default_factory=list)
    preview: dict[str, Any] | None = None
    next_question: str | None = None

    model_config = ConfigDict(extra="allow")

class AIChatResponseData(BaseModel):
    message: str
    type: str
    intent: AIIntentResponse | dict[str, Any]
    answer: str
    service_province: str | None = None
    service_location_id: int | None = None
    service_address: str | None = None
    max_price: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    max_distance_km: float | None = None
    scheduled_start_time: datetime | None = None
    scheduled_end_time: datetime | None = None
    candidate_provider_ids: list[int] = Field(default_factory=list)

    extracted_need: dict[str, Any] | None = None
    recommendation_count: int | None = None
    recommendations: list[dict[str, Any]] | None = None
    no_core_tag_matched: bool | None = None
    query: str | None = None
    capabilities: list[str] | None = None

    review_context_source: str | None = None
    review_context: Any = None

    chat_room: dict[str, Any] | None = None
    chat_room_created: bool | None = None

    booking: dict[str, Any] | None = None
    status_explanation: Any = None
    recent_status_histories: list[dict[str, Any]] | None = None
    payments: list[dict[str, Any]] | None = None
    refund_requests: list[dict[str, Any]] | None = None

    topic: str | None = None
    flow_steps: list[Any] | None = None
    statuses: Any = None

    pending_action: dict[str, Any] | None = None
    confirmation_card: AIConfirmationCardResponse | dict[str, Any] | None = None

    booking_draft: AIBookingDraftResponse | dict[str, Any] | None = None
    booking_draft_status: str | None = None
    booking_draft_preview: dict[str, Any] | None = None
    missing_fields: list[AIBookingDraftMissingFieldResponse | dict[str, Any]] | None = (
        None
    )
    provider_choices: list[dict[str, Any]] | None = None
    next_question: str | None = None

    tool_error: AIToolErrorData | dict[str, Any] | None = None
    pending_clarification: AIPendingClarificationResponse | dict[str, Any] | None = None
    tool_calls: list[AIToolCallResponse | dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] | None = None

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "message": "I will quote 120 for this booking",
                "type": "ai_action_confirmation",
                "intent": {
                    "intent": "quote_booking",
                    "confidence": 1,
                    "reason": "LangChain tool calling chose prepare_quote_booking_action",
                },
                "answer": "I prepared: submit quote. Review the details below; nothing runs until you confirm.",
                "pending_action": {
                    "id": 12,
                    "action_type": "quote_booking",
                    "status": "pending",
                    "summary": "Quote 120 for booking 3",
                },
                "confirmation_card": {
                    "ui_type": "confirmation_card",
                    "action_id": 12,
                    "action_type": "quote_booking",
                    "title": "Submit quote",
                    "status": "pending",
                    "expires_at": "2026-09-02T12:30:00",
                    "fields": [{"label": "Quote amount", "value": 120}],
                    "confirm_label": "Confirm quote",
                    "cancel_label": "Cancel",
                    "confirm_endpoint": "/ai/actions/confirm",
                    "confirm_request": {"action_id": 12},
                    "cancel_endpoint": "/ai/actions/12",
                },
            }
        },
    )

class AIToolExecuteRequest(BaseModel):
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tool_name")
    @classmethod
    def validate_tool_name_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Tool name cannot be empty")

        return value

class AIToolAgentPreviewRequest(BaseModel):
    message: str
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def validate_message_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Message cannot be empty")

        return value

class AIActionType(str, Enum):
    create_booking = "create_booking"
    cancel_booking = "cancel_booking"
    request_refund = "request_refund"
    pay_booking = "pay_booking"
    reject_quote = "reject_quote"
    confirm_complete = "confirm_complete"
    reject_complete = "reject_complete"
    quote_booking = "quote_booking"
    reject_booking = "reject_booking"
    complete_booking = "complete_booking"
    approve_refund = "approve_refund"
    reject_refund = "reject_refund"

class AIPendingActionStatus(str, Enum):
    pending = "pending"
    executed = "executed"
    expired = "expired"
    cancelled = "cancelled"

class AIActionConfirmRequest(BaseModel):
    action_id: int

class AsyncTaskType(str, Enum):
    ai_chat = "ai_chat"
    review_embedding_sync = "review_embedding_sync"
    review_embedding_delete = "review_embedding_delete"
    review_embedding_full_sync = "review_embedding_full_sync"
    notification_delivery = "notification_delivery"

class AsyncTaskStatus(str, Enum):
    pending = "pending"
    started = "started"
    retry = "retry"
    success = "success"
    failed = "failed"
    revoked = "revoked"

