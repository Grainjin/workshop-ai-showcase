import json
from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from backend import models
from backend.core.clock import utc_now

MAX_LOG_JSON_LENGTH = 8000


def dump_log_json(data: Any):
    if data is None:
        return None

    text = json.dumps(jsonable_encoder(data), ensure_ascii=False, default=str)
    if len(text) <= MAX_LOG_JSON_LENGTH:
        return text

    return text[:MAX_LOG_JSON_LENGTH] + "...<truncated>"


def load_log_json(data: str | None, default: Any = None):
    if not data:
        return default

    if data.endswith("...<truncated>"):
        return {
            "truncated": True,
            "preview": data[:500],
        }

    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return default


def create_ai_tool_call_log(
    user_id: int,
    tool_name: str,
    tool_args: dict | None,
    status: str,
    duration_ms: int,
    db: Session,
    result: Any = None,
    error_message: str | None = None,
    error_type: str | None = None,
    status_code: int | None = None,
    request_message: str | None = None,
    context: dict | None = None,
):
    log = models.AIToolCallLog(
        user_id=user_id,
        tool_name=tool_name,
        tool_args_json=dump_log_json(tool_args),
        status=status,
        result_json=dump_log_json(result),
        error_message=error_message,
        error_type=error_type,
        status_code=status_code,
        duration_ms=duration_ms,
        request_message=request_message,
        context_json=dump_log_json(context),
        created_at=utc_now(),
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return log


def format_ai_tool_call_log(log: models.AIToolCallLog):
    return {
        "id": log.id,
        "user_id": log.user_id,
        "tool_name": log.tool_name,
        "tool_args": load_log_json(log.tool_args_json, {}),
        "status": log.status,
        "result": load_log_json(log.result_json),
        "error_message": log.error_message,
        "error_type": log.error_type,
        "status_code": log.status_code,
        "duration_ms": log.duration_ms,
        "request_message": log.request_message,
        "context": load_log_json(log.context_json, {}),
        "created_at": log.created_at,
    }
