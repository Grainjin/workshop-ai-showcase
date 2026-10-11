"""Admin-managed chat API keys stored under backend/certs/.

An admin-saved key overrides .env for Customer AI Chat. Embeddings still
use EMBEDDING_* / TEI and are not written here.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.ai.oauth.files import read_secret_file, write_secret_file
from backend.config import CERTS_DIR
from backend.llm_provider import PRESETS, normalize_llm_provider, resolve_llm_settings

ADMIN_KEY_PATH = CERTS_DIR / "llm_api.json"


@dataclass(frozen=True)
class ChatCredentials:
    provider: str
    api_key: str
    base_url: str
    model: str


def _preset(provider: str) -> dict[str, object]:
    preset = PRESETS.get(provider)
    if preset is None:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown provider={provider!r}. Use one of: {known}.")
    return preset


def mask_api_key(value: str) -> str:
    key = (value or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "••••"
    return f"{key[:4]}…{key[-4:]}"


def read_admin_llm() -> dict | None:
    data = read_secret_file(ADMIN_KEY_PATH)
    if not data:
        return None
    api_key = str(data.get("api_key") or "").strip()
    if not api_key:
        return None
    return data


def save_admin_llm(
    provider: str,
    api_key: str,
    base_url: str = "",
    model: str = "",
) -> dict:
    cleaned_key = (api_key or "").strip()
    if not cleaned_key:
        existing = read_admin_llm()
        if existing:
            cleaned_key = str(existing.get("api_key") or "").strip()
        if not cleaned_key:
            raise ValueError("API key is required")

    cleaned_provider = normalize_llm_provider(provider or "qwen")
    preset = _preset(cleaned_provider)
    cleaned_base_url = (base_url or "").strip()
    cleaned_model = (model or "").strip()

    if cleaned_provider == "custom" and (not cleaned_base_url or not cleaned_model):
        raise ValueError("Custom provider requires base_url and model")

    write_secret_file(
        ADMIN_KEY_PATH,
        {
            "provider": cleaned_provider,
            "api_key": cleaned_key,
            "base_url": cleaned_base_url,
            "model": cleaned_model,
        },
    )
    return key_status()


def clear_admin_llm() -> dict:
    if ADMIN_KEY_PATH.is_file():
        ADMIN_KEY_PATH.unlink()
    return key_status()


def key_status() -> dict:
    env = resolve_llm_settings()
    admin = read_admin_llm()
    if admin:
        provider = normalize_llm_provider(str(admin.get("provider") or "qwen"))
        preset = _preset(provider)
        return {
            "configured": True,
            "source": "admin",
            "provider": provider,
            "model": str(admin.get("model") or "").strip() or str(preset["model"]),
            "base_url": str(admin.get("base_url") or "").strip()
            or str(preset["base_url"]),
            "api_key_preview": mask_api_key(str(admin.get("api_key") or "")),
        }

    if env.api_key:
        return {
            "configured": True,
            "source": "env",
            "provider": env.provider,
            "model": env.model,
            "base_url": env.base_url,
            "api_key_preview": mask_api_key(env.api_key),
        }

    return {
        "configured": False,
        "source": "none",
        "provider": env.provider,
        "model": env.model,
        "base_url": env.base_url,
        "api_key_preview": "",
    }


def resolve_chat_settings() -> ChatCredentials:
    env = resolve_llm_settings()
    admin = read_admin_llm()
    if not admin:
        return ChatCredentials(
            provider=env.provider,
            api_key=env.api_key,
            base_url=env.base_url,
            model=env.model,
        )

    provider = normalize_llm_provider(str(admin.get("provider") or env.provider))
    preset = _preset(provider)
    return ChatCredentials(
        provider=provider,
        api_key=str(admin.get("api_key") or "").strip(),
        base_url=str(admin.get("base_url") or "").strip()
        or str(preset["base_url"])
        or env.base_url,
        model=str(admin.get("model") or "").strip()
        or str(preset["model"])
        or env.model,
    )
