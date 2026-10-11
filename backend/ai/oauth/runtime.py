from __future__ import annotations

from backend.ai.oauth.api_key import key_status
from backend.ai.oauth.chatgpt import ChatGPTOAuth
from backend.ai.oauth.files import read_secret_file, write_secret_file
from backend.ai.oauth.grok import GrokOAuth
from backend.config import CERTS_DIR, LLM_PROVIDER
from backend.llm_provider import provider_choices

chatgpt_oauth = ChatGPTOAuth(CERTS_DIR / "chatgpt_oauth.json")
grok_oauth = GrokOAuth(CERTS_DIR / "grok_oauth.json")
_ACTIVE_PATH = CERTS_DIR / "llm_auth.json"

VALID_AUTH = {"key", "chatgpt", "grok"}


def get_saved_auth() -> str:
    data = read_secret_file(_ACTIVE_PATH) or {}
    auth = str(data.get("auth") or "key").strip().lower()
    return auth if auth in VALID_AUTH else "key"


def get_saved_subscription_model(provider: str) -> str:
    data = read_secret_file(_ACTIVE_PATH) or {}
    models = data.get("models") or {}
    if not isinstance(models, dict):
        return ""
    return str(models.get(provider) or "").strip()


def set_saved_auth(auth: str, model: str = "") -> str:
    cleaned = (auth or "key").strip().lower()
    if cleaned not in VALID_AUTH:
        raise ValueError("auth must be key, chatgpt, or grok")
    if cleaned == "chatgpt" and not chatgpt_oauth.connected():
        raise ValueError("Sign in to ChatGPT first")
    if cleaned == "grok" and not grok_oauth.connected():
        raise ValueError("Sign in to Grok first")
    data = read_secret_file(_ACTIVE_PATH) or {}
    data["auth"] = cleaned
    cleaned_model = (model or "").strip()
    if cleaned_model and cleaned in {"chatgpt", "grok"}:
        models = data.get("models") if isinstance(data.get("models"), dict) else {}
        models[cleaned] = cleaned_model
        data["models"] = models
    write_secret_file(_ACTIVE_PATH, data)
    return cleaned


def get_llm_auth_mode() -> str:
    saved = get_saved_auth()
    if saved == "chatgpt" and chatgpt_oauth.connected():
        return "chatgpt"
    if saved == "grok" and grok_oauth.connected():
        return "grok"
    return "key"


def subscription_status() -> dict:
    return {
        "auth": get_llm_auth_mode(),
        "saved_auth": get_saved_auth(),
        "llm_provider": LLM_PROVIDER,
        "providers": provider_choices(),
        "key": key_status(),
        "chatgpt": {
            **chatgpt_oauth.status(),
            "model": get_saved_subscription_model("chatgpt"),
        },
        "grok": {
            **grok_oauth.status(),
            "model": get_saved_subscription_model("grok"),
        },
    }


def logout_chatgpt() -> dict:
    chatgpt_oauth.logout()
    if get_saved_auth() == "chatgpt":
        set_saved_auth("key")
    return subscription_status()


def logout_grok() -> dict:
    grok_oauth.logout()
    if get_saved_auth() == "grok":
        set_saved_auth("key")
    return subscription_status()
