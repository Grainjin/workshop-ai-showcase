"""AI client factory.

Creates OpenAI-compatible chat and embedding models from env config,
or a ChatGPT Plus subscription when an admin has signed in.
"""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from backend.ai.codex import DEFAULT_CODEX_MODEL, CodexChatModel
from backend.ai.oauth.api_key import resolve_chat_settings
from backend.ai.oauth.grok import DEFAULT_GROK_MODEL, XAI_API_BASE
from backend.ai.oauth.runtime import (
    get_llm_auth_mode,
    get_saved_subscription_model,
    grok_oauth,
)
from backend.config import (
    DEMO_MODE,
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    LLM_MAX_TOKENS,
    LLM_MAX_RETRIES,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
    WORKSHOP_PUBLIC_DEPLOYMENT,
)
from backend.llm_provider import preset_headers


def get_qwen_chat_model(
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    auth_mode = get_llm_auth_mode()
    if auth_mode == "chatgpt":
        model_name = get_saved_subscription_model("chatgpt") or DEFAULT_CODEX_MODEL
        return CodexChatModel(
            model=model_name,
            temperature=temperature if temperature is not None else LLM_TEMPERATURE,
            max_tokens=max_tokens if max_tokens is not None else LLM_MAX_TOKENS,
        )
    if auth_mode == "grok":
        model_name = get_saved_subscription_model("grok") or DEFAULT_GROK_MODEL
        return ChatOpenAI(
            model=model_name,
            api_key=grok_oauth.bearer(),
            base_url=XAI_API_BASE,
            max_tokens=LLM_MAX_TOKENS if max_tokens is None else max_tokens,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )

    chat = resolve_chat_settings()
    if not chat.api_key:
        raise ValueError(
            "LLM API key is not configured. Save a vendor key in the admin "
            "dashboard, set LLM_API_KEY, or sign in with ChatGPT or Grok."
        )

    kwargs = {
        "model": chat.model,
        "api_key": chat.api_key,
        "base_url": chat.base_url,
        "max_tokens": LLM_MAX_TOKENS if max_tokens is None else max_tokens,
        "timeout": LLM_TIMEOUT_SECONDS,
        "max_retries": LLM_MAX_RETRIES,
    }
    headers = preset_headers(chat.provider)
    if headers:
        kwargs["default_headers"] = headers
    if chat.provider not in {"openai", "grok"}:
        kwargs["temperature"] = LLM_TEMPERATURE if temperature is None else temperature
    if chat.provider == "qwen" and WORKSHOP_PUBLIC_DEPLOYMENT and DEMO_MODE:
        kwargs["extra_body"] = {"enable_thinking": False}
    return ChatOpenAI(**kwargs)


def get_qwen_embedding_model():
    if not EMBEDDING_API_KEY or not EMBEDDING_MODEL or not EMBEDDING_BASE_URL:
        raise ValueError(
            "Embeddings are not configured for this LLM provider. "
            "Set EMBEDDING_API_KEY, EMBEDDING_BASE_URL, and EMBEDDING_MODEL, "
            "or use LLM_PROVIDER=openai|qwen."
        )

    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=EMBEDDING_API_KEY,
        base_url=EMBEDDING_BASE_URL,
        dimensions=EMBEDDING_DIMENSION,
        check_embedding_ctx_length=False,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )


def get_message_content(response):
    if isinstance(response.content, str):
        return response.content

    return str(response.content)


def invoke_qwen_chat(
    messages: list,
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    model = get_qwen_chat_model(
        temperature=temperature,
        max_tokens=max_tokens,
    )
    response = model.invoke(messages)

    return get_message_content(response)


def invoke_qwen_embedding(text: str):
    embedding_model = get_qwen_embedding_model()

    return embedding_model.embed_query(text)
