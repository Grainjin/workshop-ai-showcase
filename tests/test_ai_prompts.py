import re

from backend.ai.prompts import (
    ANSWER_STYLE_RULES,
    CASUAL_CHAT_SYSTEM_PROMPT,
    REVIEW_SUMMARY_SYSTEM_PROMPT,
    TOOL_RESULT_ANSWER_SYSTEM_PROMPT,
    build_intent_classification_prompt,
    build_service_need_extraction_prompt,
)
from backend.ai.tool_calling import TOOL_CALLING_SYSTEM_PROMPT, TOOL_CHOICE_RETRY_PROMPT
from backend.constants import AI_RECOMMENDATION_PROVIDER_TAGS
from backend.utils.ai_chat_fields import BOOKING_DRAFT_CONTINUATION_PROMPT

_GLUE_RE = re.compile(r"[a-z]\.[A-Z]")


def _prompt_texts():
    return {
        "casual": CASUAL_CHAT_SYSTEM_PROMPT,
        "review": REVIEW_SUMMARY_SYSTEM_PROMPT,
        "tool_result": TOOL_RESULT_ANSWER_SYSTEM_PROMPT,
        "style": ANSWER_STYLE_RULES,
        "intent": build_intent_classification_prompt(),
        "need": build_service_need_extraction_prompt(),
        "tool_calling": TOOL_CALLING_SYSTEM_PROMPT,
        "retry": TOOL_CHOICE_RETRY_PROMPT,
        "draft": BOOKING_DRAFT_CONTINUATION_PROMPT,
    }


def _without_abbreviations(text: str) -> str:
    return text.replace("e.g.", "eg")


def test_prompts_do_not_glue_sentences():
    for name, text in _prompt_texts().items():
        match = _GLUE_RE.search(_without_abbreviations(text))
        assert match is None, f"{name} has glued sentences: {match.group(0)!r}"


def test_answer_prompts_follow_user_language_and_istanbul_try():
    for name in ("casual", "review", "tool_result", "style"):
        text = _prompt_texts()[name]
        assert "user's language" in text
        assert "TRY" in text
        if name != "style":
            assert "Istanbul" in text


def test_casual_chat_states_what_the_assistant_can_do():
    text = CASUAL_CHAT_SYSTEM_PROMPT
    assert "nearby providers" in text
    assert "reviews" in text
    assert "booking" in text


def test_intent_prompt_keeps_four_intents():
    text = build_intent_classification_prompt()
    for intent in (
        "casual_chat",
        "provider_search",
        "review_summary",
        "unknown",
    ):
        assert intent in text
    assert "even if it is not English" in text


def test_need_extractor_allows_only_core_tags():
    text = build_service_need_extraction_prompt()
    for tag in AI_RECOMMENDATION_PROVIDER_TAGS:
        assert tag in text
    assert "empty service_tags" in text
    assert "babysitter" in text


def test_tool_calling_prompt_has_four_sections_and_routing():
    text = TOOL_CALLING_SYSTEM_PROMPT
    for heading in ("## Routing", "## References", "## Drafts", "## Safety"):
        assert heading in text

    expected_tools = {
        "search_providers": "Find local providers",
        "prepare_booking_draft_action": "Book, reserve, or create an order",
        "summarize_provider_reviews": "Reviews, price, attitude, or reputation",
        "create_chat_room": "Chat with a known provider_profile_id",
        "get_booking_status": "One booking's status",
        "prepare_refund_request_action": "Request a refund",
        "prepare_pay_booking_action": "Pay or accept a quote",
    }
    for tool, clue in expected_tools.items():
        assert tool in text
        assert clue in text

    assert "Booking overrides search" in text
    assert "Do not invent provider_profile_id" in text
    assert "user's language" in text
    assert "TRY" in text


def test_booking_draft_continuation_does_not_research_providers():
    text = BOOKING_DRAFT_CONTINUATION_PROMPT
    assert "Do not call search_providers" in text
    assert "prepare_booking_draft_action" in text
    assert "user's language" in text
