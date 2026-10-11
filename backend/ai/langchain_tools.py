"""Wrap backend functions as LangChain StructuredTool.

Pydantic input models define tool parameters; `build_langchain_tools` returns
different tool lists per role so customer/provider/admin only see allowed tools.
"""

from typing import Any

from datetime import datetime

from fastapi.encoders import jsonable_encoder
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.ai.tools import (
    create_chat_room_tool,
    explain_booking_flow_tool,
    get_platform_capabilities_tool,
    get_booking_status_tool,
    prepare_approve_refund_action_tool,
    prepare_booking_draft_action_tool,
    prepare_cancel_booking_action_tool,
    prepare_confirm_complete_action_tool,
    prepare_complete_booking_action_tool,
    prepare_create_booking_action_tool,
    prepare_pay_booking_action_tool,
    prepare_quote_booking_action_tool,
    prepare_reject_booking_action_tool,
    prepare_reject_complete_action_tool,
    prepare_reject_quote_action_tool,
    prepare_reject_refund_action_tool,
    prepare_refund_request_action_tool,
    search_providers_tool,
    summarize_provider_reviews_tool,
)
from backend.constants import AI_RECOMMENDATION_PROVIDER_TAGS
from backend.services.redis_service import get_last_provider_recommendation_context
from backend.utils.ai_chat import (
    get_last_booking_draft_from_history,
    get_last_provider_recommendation_context_from_history,
)


def parse_optional_datetime(value: str | None):
    if not value:
        return None

    return datetime.fromisoformat(value)


class SearchProvidersToolInput(BaseModel):
    query: str = Field(description="User service need, e.g. kitchen pipe leak")
    service_tags: list[str] = Field(
        default_factory=list,
        description=(
            "Service tags; choose only from core tags: "
            f"{', '.join(AI_RECOMMENDATION_PROVIDER_TAGS)}."
            "Return empty array if none match; do not output synonyms."
        ),
    )
    service_province: str | None = Field(default=None, description="Service province/region")
    service_location_id: int | None = Field(
        default=None,
        description="Selected province, city, or district location ID",
    )
    max_price: float | None = Field(default=None, description="Maximum budget")
    budget_preference: str | None = Field(
        default=None,
        description="Price preference: cheap, quality, balanced, or null",
    )
    latitude: float | None = Field(default=None, description="Service latitude")
    longitude: float | None = Field(default=None, description="Service longitude")
    max_distance_km: float | None = Field(default=None, description="Max distance in km")
    scheduled_start_time: str | None = Field(
        default=None,
        description="Appointment start time, ISO string",
    )
    scheduled_end_time: str | None = Field(
        default=None,
        description="Appointment end time, ISO string",
    )
    limit: int | None = Field(default=5, description="Max providers to return")


class SummarizeProviderReviewsToolInput(BaseModel):
    question: str = Field(description="User question about reviews, price, attitude, or reputation")
    provider_ids: list[int] = Field(description="Provider profile IDs to summarize")


class CreateChatRoomToolInput(BaseModel):
    provider_profile_id: int = Field(description="Provider profile ID to open chat with")


class GetBookingStatusToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to query")


class ExplainBookingFlowToolInput(BaseModel):
    topic: str | None = Field(
        default=None,
        description="Booking flow topic, e.g. quote, payment, acceptance, refund, complaint, cancel",
    )


class GetPlatformCapabilitiesToolInput(BaseModel):
    question: str | None = Field(
        default=None,
        description="User question about AI capabilities or how to use the assistant",
    )


class PrepareCreateBookingActionToolInput(BaseModel):
    provider_profile_id: int = Field(description="Provider profile ID to book")
    service_description: str = Field(min_length=1, description="Service description")
    service_address: str = Field(min_length=1, description="Service address")
    service_latitude: float = Field(description="Service latitude")
    service_longitude: float = Field(description="Service longitude")
    scheduled_start_time: str = Field(description="Appointment start time, ISO string")
    scheduled_end_time: str = Field(description="Appointment end time, ISO string")
    chat_room_id: int | None = Field(default=None, description="Existing chat room ID, optional")


class PrepareBookingDraftActionToolInput(BaseModel):
    provider_profile_id: int | None = Field(
        default=None,
        description="Provider profile ID to book; optional if unknown",
    )
    service_description: str | None = Field(
        default=None,
        description="Service description; optional if unknown",
    )
    service_address: str | None = Field(
        default=None,
        description="Service address; optional if unknown",
    )
    service_latitude: float | None = Field(
        default=None,
        description="Service latitude; optional if unknown",
    )
    service_longitude: float | None = Field(
        default=None,
        description="Service longitude; optional if unknown",
    )
    scheduled_start_time: str | None = Field(
        default=None,
        description="Appointment start time, ISO string; optional if unknown",
    )
    scheduled_end_time: str | None = Field(
        default=None,
        description="Appointment end time, ISO string; optional if unknown",
    )
    chat_room_id: int | None = Field(default=None, description="Existing chat room ID, optional")


class PrepareCancelBookingActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to cancel")


class PrepareRefundRequestActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID for refund request")
    reason: str = Field(min_length=1, description="Refund reason")


class PreparePayBookingActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to pay quote for")
    payment_method: str = Field(
        default="iyzico_checkout", description="Payment method, default iyzico Checkout Form"
    )


class PrepareRejectQuoteActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to reject quote for")
    status_note: str = Field(min_length=1, description="Reason for rejecting quote")


class PrepareConfirmCompleteActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to confirm completion")


class PrepareRejectCompleteActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to reject completion")
    status_note: str = Field(min_length=1, description="Reason for rejecting completion")


class PrepareQuoteBookingActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to quote")
    quote_amount: float = Field(gt=0, description="Expected service amount in TRY")
    visit_fee_amount: float = Field(gt=0, description="Visit fee paid before the visit in TRY")
    quote_message: str | None = Field(default=None, description="Quote message, optional")


class PrepareRejectBookingActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to reject")
    status_note: str = Field(min_length=1, description="Reason for rejecting booking")


class PrepareCompleteBookingActionToolInput(BaseModel):
    booking_id: int = Field(description="Booking ID to mark complete")


class PrepareApproveRefundActionToolInput(BaseModel):
    refund_request_id: int = Field(description="Refund request ID to approve")


class PrepareRejectRefundActionToolInput(BaseModel):
    refund_request_id: int = Field(description="Refund request ID to reject")
    provider_note: str = Field(min_length=1, description="Reason for rejecting refund")


def build_langchain_tools(current_user: models.User, db: Session):
    def search_providers(
        query: str,
        service_tags: list[str] | None = None,
        service_province: str | None = None,
        service_location_id: int | None = None,
        max_price: float | None = None,
        budget_preference: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        max_distance_km: float | None = None,
        scheduled_start_time: str | None = None,
        scheduled_end_time: str | None = None,
        limit: int | None = 5,
    ):
        return jsonable_encoder(
            search_providers_tool(
                query=query,
                service_tags=service_tags or [],
                service_province=service_province,
                service_location_id=service_location_id,
                max_price=max_price,
                budget_preference=budget_preference,
                current_user=current_user,
                db=db,
                latitude=latitude,
                longitude=longitude,
                max_distance_km=max_distance_km,
                scheduled_start_time=parse_optional_datetime(scheduled_start_time),
                scheduled_end_time=parse_optional_datetime(scheduled_end_time),
                limit=limit,
            )
        )

    def summarize_provider_reviews(
        question: str,
        provider_ids: list[int],
    ):
        return jsonable_encoder(
            summarize_provider_reviews_tool(
                question=question,
                provider_ids=provider_ids,
                current_user=current_user,
                db=db,
            )
        )

    def create_chat_room(provider_profile_id: int):
        return jsonable_encoder(
            create_chat_room_tool(
                provider_profile_id=provider_profile_id,
                current_user=current_user,
                db=db,
            )
        )

    def get_booking_status(booking_id: int):
        return jsonable_encoder(
            get_booking_status_tool(
                booking_id=booking_id,
                current_user=current_user,
                db=db,
            )
        )

    def explain_booking_flow(topic: str | None = None):
        return jsonable_encoder(explain_booking_flow_tool(topic=topic))

    def get_platform_capabilities(question: str | None = None):
        return jsonable_encoder(get_platform_capabilities_tool(question=question))

    def prepare_create_booking_action(
        provider_profile_id: int,
        service_description: str,
        service_address: str,
        service_latitude: float,
        service_longitude: float,
        scheduled_start_time: str,
        scheduled_end_time: str,
        chat_room_id: int | None = None,
    ):
        return jsonable_encoder(
            prepare_create_booking_action_tool(
                provider_profile_id=provider_profile_id,
                chat_room_id=chat_room_id,
                service_description=service_description,
                service_address=service_address,
                service_latitude=service_latitude,
                service_longitude=service_longitude,
                scheduled_start_time=parse_optional_datetime(scheduled_start_time),
                scheduled_end_time=parse_optional_datetime(scheduled_end_time),
                current_user=current_user,
                db=db,
            )
        )

    def prepare_booking_draft_action(
        provider_profile_id: int | None = None,
        service_description: str | None = None,
        service_address: str | None = None,
        service_latitude: float | None = None,
        service_longitude: float | None = None,
        scheduled_start_time: str | None = None,
        scheduled_end_time: str | None = None,
        chat_room_id: int | None = None,
    ):
        return jsonable_encoder(
            prepare_booking_draft_action_tool(
                provider_profile_id=provider_profile_id,
                chat_room_id=chat_room_id,
                service_description=service_description,
                service_address=service_address,
                service_latitude=service_latitude,
                service_longitude=service_longitude,
                scheduled_start_time=parse_optional_datetime(scheduled_start_time),
                scheduled_end_time=parse_optional_datetime(scheduled_end_time),
                current_user=current_user,
                db=db,
                existing_draft=get_last_booking_draft_from_history(
                    current_user.id,
                    db,
                ),
                provider_choices=get_last_provider_recommendation_context(
                    current_user.id,
                )
                or get_last_provider_recommendation_context_from_history(
                    current_user.id,
                    db,
                ),
            )
        )

    def prepare_cancel_booking_action(booking_id: int):
        return jsonable_encoder(
            prepare_cancel_booking_action_tool(
                booking_id=booking_id,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_refund_request_action(
        booking_id: int,
        reason: str,
    ):
        return jsonable_encoder(
            prepare_refund_request_action_tool(
                booking_id=booking_id,
                reason=reason,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_pay_booking_action(
        booking_id: int,
        payment_method: str = "iyzico_checkout",
    ):
        return jsonable_encoder(
            prepare_pay_booking_action_tool(
                booking_id=booking_id,
                payment_method=payment_method,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_reject_quote_action(
        booking_id: int,
        status_note: str,
    ):
        return jsonable_encoder(
            prepare_reject_quote_action_tool(
                booking_id=booking_id,
                status_note=status_note,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_confirm_complete_action(booking_id: int):
        return jsonable_encoder(
            prepare_confirm_complete_action_tool(
                booking_id=booking_id,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_reject_complete_action(
        booking_id: int,
        status_note: str,
    ):
        return jsonable_encoder(
            prepare_reject_complete_action_tool(
                booking_id=booking_id,
                status_note=status_note,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_quote_booking_action(
        booking_id: int,
        quote_amount: float,
        visit_fee_amount: float,
        quote_message: str | None = None,
    ):
        return jsonable_encoder(
            prepare_quote_booking_action_tool(
                booking_id=booking_id,
                quote_amount=quote_amount,
                visit_fee_amount=visit_fee_amount,
                quote_message=quote_message,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_reject_booking_action(
        booking_id: int,
        status_note: str,
    ):
        return jsonable_encoder(
            prepare_reject_booking_action_tool(
                booking_id=booking_id,
                status_note=status_note,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_complete_booking_action(booking_id: int):
        return jsonable_encoder(
            prepare_complete_booking_action_tool(
                booking_id=booking_id,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_approve_refund_action(refund_request_id: int):
        return jsonable_encoder(
            prepare_approve_refund_action_tool(
                refund_request_id=refund_request_id,
                current_user=current_user,
                db=db,
            )
        )

    def prepare_reject_refund_action(
        refund_request_id: int,
        provider_note: str,
    ):
        return jsonable_encoder(
            prepare_reject_refund_action_tool(
                refund_request_id=refund_request_id,
                provider_note=provider_note,
                current_user=current_user,
                db=db,
            )
        )

    common_tools = [
        StructuredTool.from_function(
            func=get_platform_capabilities,
            name="get_platform_capabilities",
            description=(
                "Call when the user asks what the AI assistant can do or how to use it."
                "Also call for minor typos, synonyms, or informal phrasing."
            ),
            args_schema=GetPlatformCapabilitiesToolInput,
        ),
        StructuredTool.from_function(
            func=get_booking_status,
            name="get_booking_status",
            description="Get booking status, quote, payments, refunds, and recent history by booking_id for the current user.",
            args_schema=GetBookingStatusToolInput,
        ),
        StructuredTool.from_function(
            func=explain_booking_flow,
            name="explain_booking_flow",
            description="Explain booking flow and status rules: quotes, payment, acceptance, refunds, complaints, cancellation.",
            args_schema=ExplainBookingFlowToolInput,
        ),
    ]

    customer_tools = [
        StructuredTool.from_function(
            func=search_providers,
            name="search_providers",
            description="Search local providers by tags, region, budget, location, and schedule.",
            args_schema=SearchProvidersToolInput,
        ),
        StructuredTool.from_function(
            func=summarize_provider_reviews,
            name="summarize_provider_reviews",
            description="Summarize provider reviews: price, attitude, reputation, pros and cons.",
            args_schema=SummarizeProviderReviewsToolInput,
        ),
        StructuredTool.from_function(
            func=create_chat_room,
            name="create_chat_room",
            description="Create or reuse a chat room between the customer and provider.",
            args_schema=CreateChatRoomToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_booking_draft_action,
            name="prepare_booking_draft_action",
            description=(
                "Prepare a booking draft. Callable with partial info; returns missing fields, provider choices, and next questions."
                "If a draft exists, pass only new/changed fields; the tool merges with the previous draft."
                "When complete, returns a pending customer confirmation only — does not create the booking."
            ),
            args_schema=PrepareBookingDraftActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_create_booking_action,
            name="prepare_create_booking_action",
            description="Prepare create-booking action. Returns pending confirmation only.",
            args_schema=PrepareCreateBookingActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_cancel_booking_action,
            name="prepare_cancel_booking_action",
            description="Prepare cancel-booking action. Returns pending confirmation only.",
            args_schema=PrepareCancelBookingActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_refund_request_action,
            name="prepare_refund_request_action",
            description=(
                "Prepare refund request action. Returns pending confirmation only."
            ),
            args_schema=PrepareRefundRequestActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_pay_booking_action,
            name="prepare_pay_booking_action",
            description="Prepare pay-quote action. Returns pending confirmation only.",
            args_schema=PreparePayBookingActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_reject_quote_action,
            name="prepare_reject_quote_action",
            description="Prepare reject-quote action. Returns pending confirmation only.",
            args_schema=PrepareRejectQuoteActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_confirm_complete_action,
            name="prepare_confirm_complete_action",
            description="Prepare confirm-completion action. Returns pending confirmation only.",
            args_schema=PrepareConfirmCompleteActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_reject_complete_action,
            name="prepare_reject_complete_action",
            description="Prepare reject-completion action. Returns pending confirmation only.",
            args_schema=PrepareRejectCompleteActionToolInput,
        ),
    ]

    provider_tools = [
        StructuredTool.from_function(
            func=prepare_quote_booking_action,
            name="prepare_quote_booking_action",
            description="Prepare provider quote action. Returns pending confirmation only.",
            args_schema=PrepareQuoteBookingActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_reject_booking_action,
            name="prepare_reject_booking_action",
            description="Prepare provider reject-booking action. Returns pending confirmation only.",
            args_schema=PrepareRejectBookingActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_complete_booking_action,
            name="prepare_complete_booking_action",
            description="Prepare provider mark-complete action. Returns pending confirmation only.",
            args_schema=PrepareCompleteBookingActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_approve_refund_action,
            name="prepare_approve_refund_action",
            description="Prepare provider approve-refund action. Returns pending confirmation only.",
            args_schema=PrepareApproveRefundActionToolInput,
        ),
        StructuredTool.from_function(
            func=prepare_reject_refund_action,
            name="prepare_reject_refund_action",
            description="Prepare provider reject-refund action. Returns pending confirmation only.",
            args_schema=PrepareRejectRefundActionToolInput,
        ),
    ]

    if current_user.role == "customer":
        return [*common_tools, *customer_tools]

    if current_user.role == "provider":
        return [*common_tools, *provider_tools]

    return common_tools


def get_langchain_tool_summaries(current_user: models.User, db: Session):
    tools = build_langchain_tools(current_user, db)

    return [
        {
            "name": tool.name,
            "description": tool.description,
            "args_schema": (
                tool.args_schema.model_json_schema() if tool.args_schema else None
            ),
        }
        for tool in tools
    ]


def run_langchain_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    current_user: models.User,
    db: Session,
):
    tools = {tool.name: tool for tool in build_langchain_tools(current_user, db)}
    tool = tools.get(tool_name)

    if not tool:
        return {
            "tool_name": tool_name,
            "error": "Tool not found",
        }

    return {
        "tool_name": tool_name,
        "result": tool.invoke(tool_args),
    }
