from backend.ai.tool_calling import canned_answer_from_tool_results
from backend.utils.ai import (
    CASUAL_LOCAL_ANSWER,
    looks_like_capability_question,
    looks_like_casual_greeting_only,
)


def test_capability_question_matches_whole_message_only():
    assert looks_like_capability_question("who are you")
    assert looks_like_capability_question("What can you do?")
    assert looks_like_capability_question("你是谁")
    assert not looks_like_capability_question("who are you and find a plumber")
    assert not looks_like_capability_question("I need a plumber")


def test_casual_greeting_does_not_eat_real_requests():
    assert looks_like_casual_greeting_only("hi")
    assert looks_like_casual_greeting_only("Hello!")
    assert looks_like_casual_greeting_only("merhaba")
    assert not looks_like_casual_greeting_only("hi I need a plumber")
    assert not looks_like_casual_greeting_only("who are you")


def test_canned_answer_requires_every_tool_result():
    assert (
        canned_answer_from_tool_results(
            [{"result": {"answer": "Here is what I can help with."}}]
        )
        == "Here is what I can help with."
    )
    assert canned_answer_from_tool_results([{"result": {"count": 3}}]) is None
    assert canned_answer_from_tool_results([{"error": "failed"}]) is None


def test_who_are_you_skips_llm(client, marketplace, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("tool calling should not run for capability questions")

    monkeypatch.setattr(
        "backend.utils.ai_chat_handler.choose_and_run_langchain_tools",
        boom,
    )
    response = client.post(
        "/ai/chat/sync",
        json={"message": "who are you"},
        headers=marketplace["customer"]["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["type"] == "platform_capabilities"
    assert "recommend" in body["answer"].lower() or "booking" in body["answer"].lower()


def test_hello_uses_local_casual_answer(client, marketplace, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("tool calling should not run for greetings")

    monkeypatch.setattr(
        "backend.utils.ai_chat_handler.choose_and_run_langchain_tools",
        boom,
    )
    response = client.post(
        "/ai/chat/sync",
        json={"message": "hi"},
        headers=marketplace["customer"]["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["type"] == "casual_chat"
    assert body["answer"] == CASUAL_LOCAL_ANSWER
