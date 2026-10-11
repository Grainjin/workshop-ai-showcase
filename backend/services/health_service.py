"""Read-only readiness checks, with fixed public fields and no vendor calls."""

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend import config, database
from backend.ai.oauth.api_key import resolve_chat_settings
from backend.ai.oauth.runtime import get_llm_auth_mode


def readiness_status() -> dict:
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_available = True
    except SQLAlchemyError:
        # Driver errors can include credentials and connection URLs.
        database_available = False

    try:
        ai_configured = get_llm_auth_mode() in {"chatgpt", "grok"} or bool(
            resolve_chat_settings().api_key
        )
    except (ValueError, OSError):
        ai_configured = False

    degraded_services = []
    if not database_available:
        degraded_services.append("database")
    if not ai_configured:
        degraded_services.append("ai")

    return {
        "status": "not_ready" if not database_available else "degraded" if degraded_services else "ready",
        "ready": database_available,
        "database": "available" if database_available else "unavailable",
        "demo_mode": config.DEMO_MODE,
        "payment_mode": config.PAYMENT_MODE,
        "ai_configured": ai_configured,
        "degraded_services": degraded_services,
    }
