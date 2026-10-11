"""Fetch chat model IDs from official vendor and subscription APIs."""

from __future__ import annotations

import httpx

from backend.ai.codex import DEFAULT_CODEX_MODEL
from backend.ai.oauth.api_key import read_admin_llm
from backend.ai.oauth.chatgpt import CHATGPT_CLIENT_VERSION, CHATGPT_CODEX_URL, USER_AGENT
from backend.ai.oauth.grok import DEFAULT_GROK_MODEL, XAI_API_BASE
from backend.ai.oauth.http import get_json
from backend.ai.oauth.runtime import chatgpt_oauth, grok_oauth
from backend.llm_provider import (
    PRESETS,
    normalize_llm_provider,
    preset_headers,
    resolve_llm_settings,
)

SKIP_TOKENS = (
    "embed",
    "tts",
    "whisper",
    "dall-e",
    "dalle",
    "image",
    "moderation",
    "audio",
    "transcribe",
    "realtime",
    "search",
)


def parse_model_ids(payload: object) -> list[str]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("data") or payload.get("models") or payload.get("items") or []
    else:
        items = []

    ids: list[str] = []
    seen: set[str] = set()
    for item in items:
        model_id = ""
        if isinstance(item, str):
            model_id = item.strip()
        elif isinstance(item, dict):
            model_id = str(
                item.get("id")
                or item.get("slug")
                or item.get("model")
                or item.get("name")
                or ""
            ).strip()
        if not model_id or model_id in seen or _skip_model(model_id):
            continue
        seen.add(model_id)
        ids.append(model_id)
    return ids


def _skip_model(model_id: str) -> bool:
    lowered = model_id.lower()
    return any(token in lowered for token in SKIP_TOKENS)


def list_key_models(provider: str, api_key: str = "", base_url: str = "") -> dict:
    cleaned_provider = normalize_llm_provider(provider or "qwen")
    preset = PRESETS.get(cleaned_provider)
    if preset is None:
        raise ValueError(f"Unknown provider={cleaned_provider!r}")

    key = (api_key or "").strip()
    host = (base_url or "").strip()
    if not key or not host:
        admin = read_admin_llm()
        if admin and normalize_llm_provider(str(admin.get("provider") or "")) == cleaned_provider:
            key = key or str(admin.get("api_key") or "").strip()
            host = host or str(admin.get("base_url") or "").strip()
        if not key or not host:
            env = resolve_llm_settings()
            if env.provider == cleaned_provider:
                key = key or env.api_key
                host = host or env.base_url
        host = host or str(preset["base_url"])

    if cleaned_provider == "custom" and (not key or not host):
        raise ValueError("Custom provider requires an API key and base URL to list models")
    if not key:
        raise ValueError("Enter an API key to load the official model list")
    if not host:
        raise ValueError("This provider has no API host")

    models = _fetch_openai_models(host, key, preset_headers(cleaned_provider))
    default = str(preset["model"] or "")
    if default and default not in models:
        models = [default, *models]
    return {
        "source": "key",
        "provider": cleaned_provider,
        "models": models,
        "default": default,
    }


def list_subscription_models(source: str) -> dict:
    cleaned = (source or "").strip().lower()
    if cleaned == "chatgpt":
        if not chatgpt_oauth.connected():
            raise ValueError("Sign in to ChatGPT first")
        models = _fetch_chatgpt_models()
        default = DEFAULT_CODEX_MODEL
        if default not in models:
            models = [default, *models]
        return {
            "source": "chatgpt",
            "provider": "chatgpt",
            "models": models,
            "default": default,
        }
    if cleaned == "grok":
        if not grok_oauth.connected():
            raise ValueError("Sign in to Grok first")
        models = _fetch_openai_models(
            XAI_API_BASE,
            grok_oauth.bearer(),
            {},
        )
        default = DEFAULT_GROK_MODEL
        if default not in models:
            models = [default, *models]
        return {
            "source": "grok",
            "provider": "grok",
            "models": models,
            "default": default,
        }
    raise ValueError("source must be chatgpt or grok")


def _fetch_openai_models(base_url: str, api_key: str, extra_headers: dict[str, str]) -> list[str]:
    host = base_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        **extra_headers,
    }
    if extra_headers.get("anthropic-version"):
        headers["x-api-key"] = api_key
    with httpx.Client(timeout=30.0) as client:
        payload = get_json(client, f"{host}/models", headers)
    return parse_model_ids(payload)


def _fetch_chatgpt_models() -> list[str]:
    token = chatgpt_oauth.bearer()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "originator": "codex_cli_rs",
        "ChatGPT-Client-Version": CHATGPT_CLIENT_VERSION,
    }
    account_id = chatgpt_oauth.account_id()
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id
    models_url = CHATGPT_CODEX_URL.rsplit("/", 1)[0] + f"/models?client_version={CHATGPT_CLIENT_VERSION}"
    with httpx.Client(timeout=30.0) as client:
        payload = get_json(client, models_url, headers)
    return parse_model_ids(payload)
