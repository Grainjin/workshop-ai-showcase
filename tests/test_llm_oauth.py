import base64
import json
import os
import stat

import pytest

from backend.ai.codex import (
    collapse_responses_stream,
    langchain_messages_to_codex_input,
    parse_codex_result,
)
from backend.ai.oauth import runtime
from backend.ai.oauth import api_key as llm_api_key
from backend.ai.oauth.chatgpt import account_id_from_jwt
from backend.ai.oauth.files import read_secret_file, write_secret_file
from backend.ai.oauth.http import OAuthProtocolError, raise_for_oauth_body


class _Msg:
    def __init__(self, msg_type, content, **extra):
        self.type = msg_type
        self.content = content
        for key, value in extra.items():
            setattr(self, key, value)


def _jwt(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return "h." + base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=") + ".sig"


def test_account_id_from_jwt():
    assert account_id_from_jwt(_jwt({"chatgpt_account_id": "acct_123"})) == "acct_123"
    assert (
        account_id_from_jwt(
            _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct_nested"}})
        )
        == "acct_nested"
    )


def test_collapse_responses_stream_uses_completed_event():
    stream = "\n".join(
        [
            'data: {"type":"response.created","response":{"id":"1","output":[]}}',
            'data: {"type":"response.output_text.delta","delta":"Hello"}',
            'data: {"type":"response.completed","response":{"id":"1","output":[{"type":"message","content":[{"type":"output_text","text":"Hello"}]}]}}',
            "data: [DONE]",
        ]
    )
    result = collapse_responses_stream(stream)
    assert result["output"][0]["content"][0]["text"] == "Hello"


def test_collapse_responses_stream_rebuilds_empty_output():
    stream = "\n".join(
        [
            'data: {"type":"response.created","response":{"id":"1","output":[]}}',
            'data: {"type":"response.output_text.delta","delta":"Hi"}',
            'data: {"type":"response.completed","response":{"id":"1","output":[]}}',
        ]
    )
    result = collapse_responses_stream(stream)
    assert result["output"][0]["content"][0]["text"] == "Hi"


def test_langchain_messages_to_codex_input():
    items, instructions = langchain_messages_to_codex_input(
        [
            _Msg("system", "You are helpful."),
            _Msg("human", "Find a plumber"),
        ]
    )
    assert instructions == "You are helpful."
    assert items == [{"role": "user", "content": "Find a plumber"}]


def test_parse_codex_result_function_call():
    result = parse_codex_result(
        {
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "search_providers",
                    "arguments": '{"query":"plumber"}',
                }
            ]
        }
    )
    assert result.content == ""
    assert result.tool_calls == [
        {
            "id": "call_1",
            "name": "search_providers",
            "args": {"query": "plumber"},
        }
    ]


def test_raise_for_oauth_pending():
    with pytest.raises(OAuthProtocolError) as caught:
        raise_for_oauth_body(
            400,
            b'{"error":"authorization_pending","error_description":"wait"}',
        )
    assert caught.value.code == "authorization_pending"
    assert caught.value.status == 400


def test_write_secret_file_is_owner_only(tmp_path):
    path = tmp_path / "token.json"
    write_secret_file(path, {"access": "secret"})
    assert read_secret_file(path) == {"access": "secret"}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_auth_mode_requires_connected_subscription(monkeypatch):
    monkeypatch.setattr(runtime, "get_saved_auth", lambda: "chatgpt")
    monkeypatch.setattr(runtime.chatgpt_oauth, "connected", lambda: False)
    assert runtime.get_llm_auth_mode() == "key"

    monkeypatch.setattr(runtime.chatgpt_oauth, "connected", lambda: True)
    assert runtime.get_llm_auth_mode() == "chatgpt"

    monkeypatch.setattr(runtime, "get_saved_auth", lambda: "grok")
    monkeypatch.setattr(runtime.grok_oauth, "connected", lambda: False)
    assert runtime.get_llm_auth_mode() == "key"
    monkeypatch.setattr(runtime.grok_oauth, "connected", lambda: True)
    assert runtime.get_llm_auth_mode() == "grok"


def test_set_saved_auth_rejects_disconnected(monkeypatch):
    monkeypatch.setattr(runtime.chatgpt_oauth, "connected", lambda: False)
    with pytest.raises(ValueError, match="Sign in to ChatGPT first"):
        runtime.set_saved_auth("chatgpt")
    monkeypatch.setattr(runtime.grok_oauth, "connected", lambda: False)
    with pytest.raises(ValueError, match="Sign in to Grok first"):
        runtime.set_saved_auth("grok")


def test_set_saved_auth_rejects_unknown_mode():
    with pytest.raises(ValueError, match="auth must be key, chatgpt, or grok"):
        runtime.set_saved_auth("mistral")


def test_mask_api_key():
    assert llm_api_key.mask_api_key("") == ""
    assert llm_api_key.mask_api_key("short") == "••••"
    assert llm_api_key.mask_api_key("sk-admin-test-key") == "sk-a…-key"


def test_admin_llm_key_overrides_env(tmp_path, monkeypatch):
    path = tmp_path / "llm_api.json"
    monkeypatch.setattr(llm_api_key, "ADMIN_KEY_PATH", path)
    monkeypatch.setenv("LLM_PROVIDER", "qwen")
    monkeypatch.setenv("LLM_API_KEY", "env-key-should-lose")

    status = llm_api_key.save_admin_llm("openai", "sk-admin-saved-key")
    assert status["source"] == "admin"
    assert status["provider"] == "openai"
    assert status["api_key_preview"] == "sk-a…-key"
    assert "sk-admin-saved-key" not in status["api_key_preview"]

    chat = llm_api_key.resolve_chat_settings()
    assert chat.provider == "openai"
    assert chat.api_key == "sk-admin-saved-key"
    assert chat.base_url == "https://api.openai.com/v1"

    cleared = llm_api_key.clear_admin_llm()
    assert cleared["source"] == "env"
    assert llm_api_key.resolve_chat_settings().api_key == "env-key-should-lose"


def test_custom_admin_key_requires_host_and_model(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_api_key, "ADMIN_KEY_PATH", tmp_path / "llm_api.json")
    with pytest.raises(ValueError, match="base_url and model"):
        llm_api_key.save_admin_llm("custom", "token", base_url="", model="")


def test_save_admin_llm_keeps_existing_key_when_blank(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_api_key, "ADMIN_KEY_PATH", tmp_path / "llm_api.json")
    llm_api_key.save_admin_llm("qwen", "sk-keep-this-key")
    status = llm_api_key.save_admin_llm("qwen", "", model="qwen3.8-max")
    assert status["source"] == "admin"
    assert llm_api_key.resolve_chat_settings().api_key == "sk-keep-this-key"
    assert llm_api_key.resolve_chat_settings().model == "qwen3.8-max"


def test_parse_model_ids_skips_embeddings():
    from backend.ai.oauth.models import parse_model_ids

    ids = parse_model_ids(
        {
            "data": [
                {"id": "qwen3.8-max"},
                {"id": "text-embedding-v4"},
                {"slug": "gpt-5.5"},
                {"id": "whisper-1"},
            ]
        }
    )
    assert ids == ["qwen3.8-max", "gpt-5.5"]
