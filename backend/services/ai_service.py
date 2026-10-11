"""AI service functions.

Direct Qwen calls: chat, intent classification, need extraction, review summary, embeddings.
Tool selection and execution lives in `ai/tool_calling.py`.
"""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.ai.clients import invoke_qwen_chat, invoke_qwen_embedding
from backend.ai.parsers import (
    get_default_intent_result,
    get_default_service_need_result,
    intent_parser,
    normalize_intent_result,
    normalize_service_need_result,
    service_need_parser,
)
from backend.ai.prompts import (
    CASUAL_CHAT_SYSTEM_PROMPT,
    REVIEW_SUMMARY_SYSTEM_PROMPT,
    TOOL_RESULT_ANSWER_SYSTEM_PROMPT,
    build_intent_classification_prompt,
    build_service_need_extraction_prompt,
)


def test_qwen_chat():
    return invoke_qwen_chat(
        [
            HumanMessage(content="Answer in one sentence: What is Workshop AI?"),
        ]
    )


def generate_embedding(text: str):
    return invoke_qwen_embedding(text)


def classify_user_intent(message: str):
    content = invoke_qwen_chat(
        [
            SystemMessage(content=build_intent_classification_prompt()),
            HumanMessage(content=message),
        ],
        temperature=0,
        max_tokens=200,
    )

    try:
        result = intent_parser.parse(content)
    except Exception:
        return get_default_intent_result()

    return normalize_intent_result(result)


def build_chat_history_messages(chat_history: list[dict] | None):
    if not chat_history:
        return []

    messages = []

    for item in chat_history:
        role = item.get("role")
        content = item.get("content")

        if not content:
            continue

        if role == "user":
            messages.append(HumanMessage(content=content))

        if role == "assistant":
            messages.append(AIMessage(content=content))

    return messages


def generate_casual_chat_response(
    message: str,
    chat_history: list[dict] | None = None,
):
    messages = [SystemMessage(content=CASUAL_CHAT_SYSTEM_PROMPT)]
    messages.extend(build_chat_history_messages(chat_history))
    messages.append(HumanMessage(content=message))

    return invoke_qwen_chat(messages, max_tokens=200)


def extract_service_need(message: str):
    content = invoke_qwen_chat(
        [
            SystemMessage(content=build_service_need_extraction_prompt()),
            HumanMessage(content=message),
        ],
        temperature=0,
        max_tokens=300,
    )

    try:
        result = service_need_parser.parse(content)
    except Exception:
        return get_default_service_need_result()

    return normalize_service_need_result(result)


def summarize_provider_reviews(
    message: str,
    review_context: list[dict],
    chat_history: list[dict] | None = None,
):
    messages = [SystemMessage(content=REVIEW_SUMMARY_SYSTEM_PROMPT)]
    messages.extend(build_chat_history_messages(chat_history))
    messages.append(
        HumanMessage(
            content=(
                "User question: "
                + message
                + "\n\nCandidate provider review data: "
                + json.dumps(review_context, ensure_ascii=False)
            ),
        )
    )

    return invoke_qwen_chat(messages)


def generate_tool_result_answer(
    message: str,
    tool_name: str,
    tool_args: dict,
    tool_result: dict,
    chat_history: list[dict] | None = None,
    fallback_answer: str | None = None,
):
    messages = [SystemMessage(content=TOOL_RESULT_ANSWER_SYSTEM_PROMPT)]
    messages.extend(build_chat_history_messages(chat_history))
    messages.append(
        HumanMessage(
            content=(
                "User message: "
                + message
                + "\n\nTool name: "
                + tool_name
                + "\n\nTool args: "
                + json.dumps(tool_args, ensure_ascii=False)
                + "\n\nTool result: "
                + json.dumps(tool_result, ensure_ascii=False)
            ),
        )
    )

    try:
        return invoke_qwen_chat(messages, max_tokens=300)
    except Exception:
        return fallback_answer or "I completed the query based on your request."
