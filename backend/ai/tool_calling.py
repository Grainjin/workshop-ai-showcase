"""LangChain tool-calling flow.

The model decides whether to call tools from user input and context. After
execution, canned tool answers are used when present; the chat handler otherwise
formats the reply. All tool calls are logged to `ai_tool_call_logs`.
"""

from typing import Any

import json
import time

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend import models
from backend.ai.clients import get_message_content, get_qwen_chat_model
from backend.ai.langchain_tools import build_langchain_tools
from backend.utils.ai_tool_log import create_ai_tool_call_log

TOOL_CALLING_SYSTEM_PROMPT = """You are Workshop AI's tool-calling assistant. Choose tools from the user message and context. Do not name a chat vendor or model.

## Routing
- Find local providers: search_providers. service_tags must be core tags only: cleaning, childcare, elderly_care, electrician, plumbing, painter, locksmith, technician, moving. Never map unknown needs to other; use an empty array.
- Book, reserve, or create an order: prepare_booking_draft_action only. Do not call search_providers. Booking overrides search.
- Reviews, price, attitude, or reputation: summarize_provider_reviews.
- Chat with a known provider_profile_id: create_chat_room.
- One booking's status, quote, payment, refund, or next step: get_booking_status.
- How booking, quotes, payment, refunds, complaints, or cancellation work: explain_booking_flow.
- What you can do or how to use you, including minor typos: get_platform_capabilities.
- Cancel a booking: prepare_cancel_booking_action (confirmation draft only).
- Request a refund: prepare_refund_request_action with booking_id and reason after the booking is completed.
- Pay or accept a quote: prepare_pay_booking_action.
- Reject a quote: prepare_reject_quote_action.
- Confirm completion: prepare_confirm_complete_action.
- Reject completion: prepare_reject_complete_action.
- Provider quote: prepare_quote_booking_action.
- Provider reject booking: prepare_reject_booking_action.
- Provider mark complete: prepare_complete_booking_action.
- Provider approve refund: prepare_approve_refund_action.
- Provider reject refund: prepare_reject_refund_action.

## References
- actionable_context lists bookings or refund requests the user can act on.
- Phrases like "this booking", "that order", or "this refund" fill booking_id or refund_request_id from that list.
- Auto-fill an id only when there is one candidate or the user clearly points at one record. Otherwise ask. Do not guess.
- If the action is clear but the id is missing, call the tool with known args; the backend returns choices.
- "first one" or "number 1" with recommended_provider_context or candidate_provider_ids: use that index for prepare_booking_draft_action, create_chat_room, or summarize_provider_reviews.
- If booking_draft lacks provider_profile_id and the user picks by rank or price, they are choosing from recommended_provider_context.

## Drafts
- Prefer prepare_booking_draft_action even with partial info. It returns missing fields, provider choices, and next questions. A confirmation draft only when complete.
- If booking_draft exists and the user changes provider, address, time, or description, call it with only the new fields.
- If the user cancels the draft ("start over", "never mind", "don't book"), do not continue booking; the backend clears the draft.
- Relative dates (today, tomorrow) with current_date: convert to ISO datetimes. If date or time is unclear, leave fields empty.
- Only call prepare_create_booking_action when provider_profile_id, description, address, location, and times are all explicit. It only creates a pending confirmation. Never say the order already exists.

## Safety
- Do not invent provider_profile_id, address, coordinates, or appointment times.
- All database-changing actions require user confirmation first.
- If draft_status=missing_info or missing_fields is present, ask the missing_fields questions. Do not say booking or payment can proceed.
- If information is insufficient, do not invent parameters; say what is still needed.
- When you speak to the user, reply in the user's language. Quote money in TRY.
"""

TOOL_CHOICE_RETRY_PROMPT = (
    "The last tool choice invoked no tools and returned an empty reply. "
    "Re-evaluate. "
    "Follow system rules, the user message, and context to pick the best tool. "
    "If no tool fits, reply in the user's language about what information is still needed. "
    "Do not invent parameters or call tools unnecessarily."
)


def build_tool_calling_user_message(
    message: str,
    context: dict[str, Any] | None = None,
):
    if not context:
        return message

    return (
        f"User message: {message}\n\n"
        "Available context: "
        f"{json.dumps(context, ensure_ascii=False)}"
    )


def canned_answer_from_tool_results(tool_results: list[dict[str, Any]]) -> str | None:
    answers = []
    for tool_result in tool_results:
        if tool_result.get("error"):
            return None
        payload = tool_result.get("result") or {}
        if not isinstance(payload, dict):
            return None
        answer = str(payload.get("answer") or "").strip()
        if not answer:
            return None
        answers.append(answer)
    if not answers:
        return None
    return "\n\n".join(answers)


def should_retry_empty_tool_choice(response):
    return not response.tool_calls and not get_message_content(response).strip()


def select_langchain_tools(
    current_user: models.User,
    db: Session,
    allowed_tool_names: list[str] | None = None,
):
    tools = build_langchain_tools(current_user, db)

    if allowed_tool_names is None:
        return tools

    allowed_tool_name_set = set(allowed_tool_names)
    return [tool for tool in tools if tool.name in allowed_tool_name_set]


def get_business_error_code(status_code: int | None, detail: Any):
    detail_text = str(detail or "").lower()

    if status_code == 401:
        return "UNAUTHENTICATED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        if "provider" in detail_text:
            return "PROVIDER_NOT_FOUND"
        if "booking" in detail_text:
            return "BOOKING_NOT_FOUND"
        if "refund" in detail_text:
            return "REFUND_REQUEST_NOT_FOUND"
        if "chat" in detail_text:
            return "CHAT_ROOM_NOT_FOUND"
        return "RESOURCE_NOT_FOUND"
    if status_code == 422:
        return "VALIDATION_ERROR"
    if status_code == 400:
        if "approved" in detail_text and "provider" in detail_text:
            return "PROVIDER_NOT_APPROVED"
        if "latitude" in detail_text or "longitude" in detail_text:
            return "MISSING_LOCATION"
        if "available" in detail_text:
            return "PROVIDER_NOT_AVAILABLE"
        if (
            "pending" in detail_text
            or "quoted" in detail_text
            or "status" in detail_text
        ):
            return "BOOKING_STATUS_NOT_ALLOWED"
        if "reason" in detail_text:
            return "REASON_REQUIRED"
        return "BAD_REQUEST"

    return "TOOL_EXECUTION_ERROR"


def format_tool_error(error: Exception):
    if isinstance(error, HTTPException):
        return {
            "error": str(error.detail),
            "error_code": get_business_error_code(error.status_code, error.detail),
            "error_type": "http_exception",
            "status_code": error.status_code,
            "error_details": error.detail,
        }

    if isinstance(error, ValidationError):
        return {
            "error": "Tool argument validation error",
            "error_code": "VALIDATION_ERROR",
            "error_type": "validation_error",
            "status_code": 422,
            "error_details": error.errors(),
        }

    return {
        "error": str(error),
        "error_code": "TOOL_EXECUTION_ERROR",
        "error_type": error.__class__.__name__,
        "status_code": None,
        "error_details": None,
    }


def execute_langchain_tool_call(
    tool_name: str,
    tool_args: dict,
    current_user: models.User,
    db: Session,
    message: str,
    context: dict[str, Any] | None = None,
):
    """Execute one LangChain tool and log success/failure.

    Catches HTTPException, ValidationError, and other exceptions into tool_error.
    """

    tools = build_langchain_tools(current_user, db)
    tool_map = {tool.name: tool for tool in tools}
    tool = tool_map.get(tool_name)
    start_time = time.perf_counter()

    if not tool:
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        tool_result = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "error": "Tool not found",
            "error_code": "TOOL_NOT_FOUND",
            "error_type": "tool_not_found",
            "status_code": 404,
            "error_details": None,
        }
        log = create_ai_tool_call_log(
            user_id=current_user.id,
            tool_name=tool_name,
            tool_args=tool_args,
            status="failed",
            duration_ms=duration_ms,
            db=db,
            error_message=tool_result["error"],
            error_type=tool_result["error_type"],
            status_code=tool_result["status_code"],
            request_message=message,
            context=context,
        )
        tool_result["tool_call_log_id"] = log.id

        return tool_result

    try:
        result = jsonable_encoder(tool.invoke(tool_args))
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        log = create_ai_tool_call_log(
            user_id=current_user.id,
            tool_name=tool_name,
            tool_args=tool_args,
            status="success",
            duration_ms=duration_ms,
            db=db,
            result=result,
            request_message=message,
            context=context,
        )

        return {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "result": result,
            "tool_call_log_id": log.id,
        }
    except Exception as error:
        db.rollback()
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        formatted_error = format_tool_error(error)
        log = create_ai_tool_call_log(
            user_id=current_user.id,
            tool_name=tool_name,
            tool_args=tool_args,
            status="failed",
            duration_ms=duration_ms,
            db=db,
            error_message=formatted_error["error"],
            error_type=formatted_error["error_type"],
            status_code=formatted_error["status_code"],
            request_message=message,
            context=context,
        )

        return {
            "tool_name": tool_name,
            "tool_args": tool_args,
            **formatted_error,
            "tool_call_log_id": log.id,
        }


def choose_and_run_langchain_tools(
    message: str,
    current_user: models.User,
    db: Session,
    context: dict[str, Any] | None = None,
    allowed_tool_names: list[str] | None = None,
    extra_system_prompt: str | None = None,
):
    tools = select_langchain_tools(current_user, db, allowed_tool_names)
    model = get_qwen_chat_model(temperature=0, max_tokens=500).bind_tools(tools)
    messages = [
        SystemMessage(content=TOOL_CALLING_SYSTEM_PROMPT),
        HumanMessage(content=build_tool_calling_user_message(message, context)),
    ]
    if extra_system_prompt:
        messages.insert(1, SystemMessage(content=extra_system_prompt))

    first_response = model.invoke(messages)

    if should_retry_empty_tool_choice(first_response):
        retry_messages = [
            *messages,
            SystemMessage(content=TOOL_CHOICE_RETRY_PROMPT),
        ]
        first_response = model.invoke(retry_messages)
        messages = retry_messages

    tool_calls = first_response.tool_calls or []

    if not tool_calls:
        answer = get_message_content(first_response).strip()

        return {
            "message": message,
            "type": "no_tool_call",
            "answer": answer or "No suitable capability found. Please describe your need in more detail.",
            "tool_calls": [],
            "tool_results": [],
        }

    tool_results = []

    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args") or {}
        tool_result = execute_langchain_tool_call(
            tool_name,
            tool_args,
            current_user,
            db,
            message,
            context,
        )
        tool_results.append(tool_result)

    return {
        "message": message,
        "type": "tool_call",
        "answer": canned_answer_from_tool_results(tool_results),
        "tool_calls": jsonable_encoder(tool_calls),
        "tool_results": tool_results,
        "final_answer_error": None,
    }
