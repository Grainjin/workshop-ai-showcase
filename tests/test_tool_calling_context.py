"""Exercise the real booking formatter and model-context serialization boundary."""

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json

from langchain_core.messages import AIMessage, HumanMessage
import pytest

from backend import models
from backend.ai import tool_calling
from backend.utils.ai_context import format_ai_context_booking


@pytest.fixture
def booking():
    return models.Booking(
        id=301,
        status="awaiting_confirmation",
        service_description="清洁厨房 🧹",
        service_address="İstanbul，测试地址",
        scheduled_start_time=datetime(2026, 10, 20, 13, 0, 0, 123456),
        scheduled_end_time=datetime(2026, 10, 20, 14, 0, 0, 654321),
        quote_amount=Decimal("500.25"),
        quote_message="İş tamamlandı，等待确认",
        chat_room_id=1,
    )


def actionable_booking_context(booking):
    return {
        "actionable_context": {
            "awaiting_confirmation_can_confirm_or_reject": [
                format_ai_context_booking(booking)
            ],
        },
    }


@pytest.mark.parametrize(
    "tz, expected_start, expected_end",
    [
        (None, "2026-10-20T13:00:00.123456", "2026-10-20T14:00:00.654321"),
        (
            timezone.utc,
            "2026-10-20T13:00:00.123456+00:00",
            "2026-10-20T14:00:00.654321+00:00",
        ),
        (
            timezone(timedelta(hours=3)),
            "2026-10-20T13:00:00.123456+03:00",
            "2026-10-20T14:00:00.654321+03:00",
        ),
    ],
    ids=["naive", "utc", "offset"],
)
def test_real_booking_context_preserves_fields_and_timestamps(
    booking, tz, expected_start, expected_end
):
    booking.scheduled_start_time = booking.scheduled_start_time.replace(tzinfo=tz)
    booking.scheduled_end_time = booking.scheduled_end_time.replace(tzinfo=tz)
    context = actionable_booking_context(booking)
    original = deepcopy(context)
    formatted_booking = context["actionable_context"][
        "awaiting_confirmation_can_confirm_or_reject"
    ][0]

    content = tool_calling.build_tool_calling_user_message("请准备确认卡片", context)
    prefix = "User message: 请准备确认卡片\n\nAvailable context: "
    assert content.startswith(prefix)
    assert "清洁厨房 🧹" in content
    assert "İş tamamlandı，等待确认" in content
    assert json.loads(content[len(prefix):]) == {
        "actionable_context": {
            "awaiting_confirmation_can_confirm_or_reject": [{
                "booking_id": 301,
                "status": "awaiting_confirmation",
                "service_description": "清洁厨房 🧹",
                "service_address": "İstanbul，测试地址",
                "scheduled_start_time": expected_start,
                "scheduled_end_time": expected_end,
                "quote_amount": 500.25,
                "quote_message": "İş tamamlandı，等待确认",
                "chat_room_id": 1,
            }],
        },
    }
    assert context == original
    assert formatted_booking["scheduled_start_time"] is booking.scheduled_start_time
    assert formatted_booking["scheduled_end_time"] is booking.scheduled_end_time
    assert isinstance(formatted_booking["quote_amount"], Decimal)


def test_nested_date_and_time_context_uses_iso_values_without_mutation():
    context = {
        "availability": [{
            "date": date(2026, 10, 20),
            "window": {
                "start": time(13, 0, 0, 123456),
                "end": time(14, 0, 0, 654321, tzinfo=timezone(timedelta(hours=3))),
            },
        }],
    }
    original = deepcopy(context)

    content = tool_calling.build_tool_calling_user_message("查可用时间", context)

    assert json.loads(content.split("Available context: ", 1)[1]) == {
        "availability": [{
            "date": "2026-10-20",
            "window": {
                "start": "13:00:00.123456",
                "end": "14:00:00.654321+03:00",
            },
        }],
    }
    assert context == original


@pytest.mark.parametrize("context", [None, {}])
def test_absent_context_preserves_user_message(context):
    assert tool_calling.build_tool_calling_user_message("  你好 🧹\n", context) == "  你好 🧹\n"


def test_omitted_context_preserves_user_message():
    assert tool_calling.build_tool_calling_user_message("你好") == "你好"


def test_plain_json_context_preserves_existing_message_format():
    context = {"booking_id": 301, "label": "订单 🧹", "active": True, "note": None}

    assert tool_calling.build_tool_calling_user_message("请确认", context) == (
        'User message: 请确认\n\nAvailable context: '
        '{"booking_id": 301, "label": "订单 🧹", "active": true, "note": null}'
    )


def test_unsupported_context_object_is_not_silently_stringified():
    with pytest.raises((TypeError, ValueError)):
        tool_calling.build_tool_calling_user_message("请确认", {"unsupported": object()})


def test_orchestrator_delivers_real_booking_context_to_model(booking, monkeypatch):
    context = actionable_booking_context(booking)
    received_messages = []

    class LocalModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            received_messages.append(messages)
            return AIMessage(content="请查看确认卡片")

    # Replace only the external model; keep tool selection and prompt building real.
    monkeypatch.setattr(tool_calling, "get_qwen_chat_model", lambda **kwargs: LocalModel())

    result = tool_calling.choose_and_run_langchain_tools(
        "请准备订单 301 的确认卡片",
        models.User(id=2, role="customer"),
        None,
        context=context,
    )

    assert result == {
        "message": "请准备订单 301 的确认卡片",
        "type": "no_tool_call",
        "answer": "请查看确认卡片",
        "tool_calls": [],
        "tool_results": [],
    }
    assert len(received_messages) == 1
    user_message = next(
        message for message in received_messages[0] if isinstance(message, HumanMessage)
    )
    serialized = json.loads(user_message.content.split("Available context: ", 1)[1])
    delivered_booking = serialized["actionable_context"][
        "awaiting_confirmation_can_confirm_or_reject"
    ][0]
    assert delivered_booking["booking_id"] == 301
    assert delivered_booking["scheduled_start_time"] == "2026-10-20T13:00:00.123456"
    assert delivered_booking["scheduled_end_time"] == "2026-10-20T14:00:00.654321"
    assert delivered_booking["service_description"] == "清洁厨房 🧹"
