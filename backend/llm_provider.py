"""Resolve chat and embedding settings for OpenAI-compatible LLM vendors.

ChatGPT Plus can authenticate with a device-code login. Qwen and OpenAI API
keys also provide embeddings for review search.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

QWEN_DEFAULT_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

PROVIDER_ALIASES = {
    "gpt": "openai",
    "chatgpt": "openai",
    "dashscope": "qwen",
    "aliyun": "qwen",
    "qwen": "qwen",
    "openai": "openai",
    "anthropic": "claude",
    "claude": "claude",
    "moonshot": "kimi",
    "kimi": "kimi",
    "kimi-global": "kimi",
    "kimi-code": "kimi-code",
    "kimi-coding": "kimi-code",
    "deepseek": "deepseek",
    "xai": "grok",
    "grok": "grok",
    "custom": "custom",
}

PRESETS: dict[str, dict[str, object]] = {
    "qwen": {
        "label": "Qwen",
        "base_url": QWEN_DEFAULT_BASE_URL,
        "model": "qwen3.8-max",
        "key_env": ("QWEN_API_KEY", "DASHSCOPE_API_KEY", "LLM_API_KEY"),
        "embedding_model": "text-embedding-v4",
        "embedding_dimension": 1024,
        "headers": {},
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-6-astra",
        "key_env": ("OPENAI_API_KEY", "LLM_API_KEY"),
        "embedding_model": "text-embedding-3-large",
        "embedding_dimension": 1024,
        "headers": {},
    },
    "claude": {
        "label": "Claude",
        "base_url": "https://api.anthropic.com/v1",
        "model": "claude-sonnet-5",
        "key_env": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "LLM_API_KEY"),
        "embedding_model": "",
        "embedding_dimension": 1024,
        "headers": {"anthropic-version": "2023-06-01"},
    },
    "kimi": {
        "label": "Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k3",
        "key_env": ("KIMI_API_KEY", "MOONSHOT_API_KEY", "LLM_API_KEY"),
        "embedding_model": "",
        "embedding_dimension": 1024,
        "headers": {},
    },
    "kimi-code": {
        "label": "Kimi Code",
        "base_url": "https://api.kimi.com/coding/v1",
        "model": "k3",
        "key_env": ("KIMI_CODE_API_KEY", "KIMI_API_KEY", "LLM_API_KEY"),
        "embedding_model": "",
        "embedding_dimension": 1024,
        "headers": {},
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_env": ("DEEPSEEK_API_KEY", "LLM_API_KEY"),
        "embedding_model": "",
        "embedding_dimension": 1024,
        "headers": {},
    },
    "grok": {
        "label": "Grok",
        "base_url": "https://api.x.ai/v1",
        "model": "grok-4.7",
        "key_env": ("XAI_API_KEY", "GROK_API_KEY", "LLM_API_KEY"),
        "embedding_model": "",
        "embedding_dimension": 1024,
        "headers": {},
    },
    "custom": {
        "label": "Custom",
        "base_url": "",
        "model": "",
        "key_env": ("LLM_API_KEY",),
        "embedding_model": "",
        "embedding_dimension": 1024,
        "headers": {},
    },
}


def provider_choices() -> list[dict[str, str]]:
    return [
        {"id": provider, "label": str(preset["label"])}
        for provider, preset in PRESETS.items()
    ]


def preset_headers(provider: str) -> dict[str, str]:
    preset = PRESETS.get(normalize_llm_provider(provider))
    if not preset:
        return {}
    headers = preset.get("headers") or {}
    if not isinstance(headers, dict):
        return {}
    return {str(key): str(value) for key, value in headers.items()}


@dataclass(frozen=True)
class LlmSettings:
    provider: str
    api_key: str
    base_url: str
    model: str
    embedding_api_key: str
    embedding_base_url: str
    embedding_model: str
    embedding_dimension: int
    supports_embeddings: bool


def _env(name: str, getenv) -> str:
    value = getenv(name)
    if value is None or not str(value).strip():
        return ""
    return str(value).strip()


def normalize_llm_provider(value: str) -> str:
    provider = (value or "qwen").strip().lower()
    return PROVIDER_ALIASES.get(provider, provider)


def first_env(names: tuple[str, ...], getenv) -> str:
    for name in names:
        value = _env(name, getenv)
        if value:
            return value
    return ""


def resolve_llm_settings(getenv=os.getenv) -> LlmSettings:
    provider = normalize_llm_provider(_env("LLM_PROVIDER", getenv) or "qwen")
    preset = PRESETS.get(provider)
    if preset is None:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(
            f"Unknown LLM_PROVIDER={provider!r}. Use one of: {known}."
        )

    key_env = preset["key_env"]
    assert isinstance(key_env, tuple)

    api_key = first_env(key_env, getenv)
    base_url = _env("LLM_BASE_URL", getenv) or str(preset["base_url"])
    model = _env("LLM_MODEL", getenv) or str(preset["model"])

    embedding_api_key = (
        _env("EMBEDDING_API_KEY", getenv)
        or first_env(("OPENAI_API_KEY", "QWEN_API_KEY", "DASHSCOPE_API_KEY"), getenv)
        or api_key
    )
    embedding_base_url = _env("EMBEDDING_BASE_URL", getenv) or base_url
    embedding_model = _env("EMBEDDING_MODEL", getenv) or str(preset["embedding_model"])
    embedding_dimension_raw = _env("EMBEDDING_DIMENSION", getenv)
    embedding_dimension = (
        int(embedding_dimension_raw)
        if embedding_dimension_raw
        else int(preset["embedding_dimension"])
    )

    return LlmSettings(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        supports_embeddings=bool(embedding_model and embedding_api_key),
    )
