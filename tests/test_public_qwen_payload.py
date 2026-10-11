"""Inspect real SDK request JSON locally; never contact a paid model provider."""

import json

import httpx
import pytest

from backend.ai import clients
from backend.ai.oauth.api_key import ChatCredentials


def capture_request(monkeypatch, *, provider="qwen", public=True, demo=True, auth="key"):
    monkeypatch.setattr(clients, "WORKSHOP_PUBLIC_DEPLOYMENT", public, raising=False)
    monkeypatch.setattr(clients, "DEMO_MODE", demo, raising=False)
    monkeypatch.setattr(clients, "get_llm_auth_mode", lambda: auth)
    monkeypatch.setattr(clients, "resolve_chat_settings", lambda: ChatCredentials(
        provider, "test-no-network", "https://provider.invalid/v1", "qwen3.8-flash"
    ))
    monkeypatch.setattr(clients.grok_oauth, "bearer", lambda: "test-no-network")
    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "local-response", "object": "chat.completion", "created": 1,
            "model": "qwen3.8-flash",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Local fixture"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        model = clients.get_qwen_chat_model()
        # Keep the real LangChain/OpenAI clients and serializers; replace only HTTP I/O.
        model.root_client._client = transport
        assert model.invoke("Hello").content == "Local fixture"
    assert len(requests) == 1
    return requests[0]


def test_public_demo_qwen_disables_default_thinking_in_real_wire_payload(monkeypatch):
    payload = capture_request(monkeypatch)
    assert payload["enable_thinking"] is False
    assert "extra_body" not in payload
    assert payload["model"] == "qwen3.8-flash"


@pytest.mark.parametrize("public,demo", [(False, True), (True, False), (False, False)])
def test_local_or_full_qwen_preserves_existing_payload(monkeypatch, public, demo):
    assert "enable_thinking" not in capture_request(monkeypatch, public=public, demo=demo)


@pytest.mark.parametrize("provider", ["openai", "grok", "custom"])
def test_other_api_key_providers_preserve_existing_payload(monkeypatch, provider):
    assert "enable_thinking" not in capture_request(monkeypatch, provider=provider)


def test_grok_subscription_payload_does_not_receive_qwen_options(monkeypatch):
    assert "enable_thinking" not in capture_request(monkeypatch, auth="grok")


def test_chatgpt_subscription_keeps_existing_model_class(monkeypatch):
    monkeypatch.setattr(clients, "WORKSHOP_PUBLIC_DEPLOYMENT", True, raising=False)
    monkeypatch.setattr(clients, "DEMO_MODE", True, raising=False)
    monkeypatch.setattr(clients, "get_llm_auth_mode", lambda: "chatgpt")
    monkeypatch.setattr(clients, "get_saved_subscription_model", lambda _: "local-codex-model")
    model = clients.get_qwen_chat_model()
    assert isinstance(model, clients.CodexChatModel)
    assert model.model == "local-codex-model"
