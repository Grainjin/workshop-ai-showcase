"""AI API.

AI chat, LangChain tool debugging, pending actions, async tasks, Milvus sync.
DB-changing AI ops create `AIPendingAction` first; frontend confirms via `/ai/actions/confirm`.
"""

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session
from celery.result import AsyncResult
import logging
from backend.auth import get_db, require_admin, require_verified_user
from backend.utils.payment_redirect import payment_result_url_for_request
from backend.schemas import (
    AIActionConfirmRequest,
    AIActionType,
    AIPendingActionStatus,
    AIChatRequest,
    AIChatResponseData,
    AIProviderRecommendRequest,
    AIToolAgentPreviewRequest,
    AIToolExecuteRequest,
    ApiResponse,
    AsyncTaskType,
    BookingNoteUpdate,
    BookingCreate,
    ProviderBookingQuoteCreate,
    ProviderRefundRejectCreate,
)
from backend.services.milvus_service import (
    check_milvus_connection,
    create_review_collection,
)
from backend.services.ai_service import generate_embedding, test_qwen_chat
from backend.services.redis_service import check_redis_connection
from backend.ai.oauth.api_key import clear_admin_llm, save_admin_llm
from backend.ai.oauth.models import list_key_models, list_subscription_models
from backend.ai.oauth.runtime import (
    chatgpt_oauth,
    grok_oauth,
    logout_chatgpt,
    logout_grok,
    set_saved_auth,
    subscription_status,
)
from backend import models
from backend.utils.pagination import build_paginated_response, paginate_query
from backend.ai.langchain_tools import (
    get_langchain_tool_summaries,
    run_langchain_tool,
)
from backend.ai.tool_calling import choose_and_run_langchain_tools
from backend.ai.tools import search_providers_tool
from backend.utils.ai import parse_user_service_need
from backend.utils.ai_chat import delete_ai_chat_messages, format_ai_chat_message
from backend.utils.ai_chat_handler import handle_ai_chat_request
from backend.utils.async_task import (
    create_async_task_record,
    format_async_task_response,
    sync_async_task_record_from_celery,
)
from backend.utils.customer_booking_actions import (
    cancel_customer_booking_action,
    confirm_customer_booking_complete_action,
    create_customer_booking_action,
    create_customer_refund_request_action,
    pay_customer_booking_action,
    reject_customer_booking_complete_action,
    reject_customer_booking_quote_action,
)
from backend.utils.provider_booking_actions import (
    approve_provider_refund_request_action,
    complete_provider_booking_action,
    quote_provider_booking_action,
    reject_provider_booking_action,
    reject_provider_refund_request_action,
)
from backend.utils.ai_pending_action import (
    cancel_ai_pending_action,
    expire_user_pending_actions,
    format_ai_pending_action,
    get_ai_pending_action_or_404,
    get_confirmable_ai_pending_action,
    load_json,
    mark_ai_pending_action_executed,
    refresh_ai_pending_action_expiration,
)
from backend.utils.ai_tool_log import format_ai_tool_call_log
from backend.utils.review_embedding_queue import (
    enqueue_all_review_embeddings_sync,
    enqueue_review_embedding_sync,
)
from backend.tasks.ai_tasks import ai_chat_task
from backend.tasks.celery_app import celery_app
from backend.utils.response import success_response
from backend.utils.router import ApiRouter
from backend.utils.demo_mode import DemoAIRoute, reject_demo_restricted_action
from backend.utils.demo_ai_quota import enforce_demo_ai_quota

router = ApiRouter(tags=["AI"], route_class=DemoAIRoute)
logger = logging.getLogger(__name__)


class LLMAuthUpdate(BaseModel):
    auth: str
    model: str = ""


class LLMApiKeyUpdate(BaseModel):
    provider: str = "qwen"
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class LLMModelsRequest(BaseModel):
    source: str = "key"
    provider: str = "qwen"
    api_key: str = ""
    base_url: str = ""


def is_llm_service_error(error: Exception):
    error_text = str(error).lower()

    return any(
        keyword in error_text
        for keyword in [
            "insufficient_quota",
            "free quota exhausted",
            "llm api key is not configured",
            "not signed in",
            "embeddings are not configured",
            "not signed in to chatgpt",
            "not signed in to grok",
            "invalid_api_key",
            "api-key",
            "api key",
            "authentication",
            "quota",
            "chatgpt codex error",
            "not supported when using codex",
        ]
    )


def build_ai_service_error_response(
    request_data: AIChatRequest,
    error: Exception,
    db: Session,
):
    error_text = str(error)

    if "insufficient_quota" in error_text or "Free quota exhausted" in error_text:
        answer = (
            "AI model quota exceeded; cannot call the model right now."
            "Check Qwen console balance or disable use free tier only."
        )
    elif "LLM API key is not configured" in error_text:
        answer = (
            "AI API key is not configured. Save a vendor key in the admin "
            "dashboard, or set LLM_PROVIDER and the matching vendor key."
        )
    elif "not supported when using Codex" in error_text:
        answer = (
            "This ChatGPT subscription cannot use the configured Codex model. "
            "Load official models in the admin dashboard and pick a Codex model."
        )
    else:
        answer = "AI service is temporarily unavailable. Please try again later."

    return {
        "message": request_data.message,
        "type": "ai_service_error",
        "intent": {
            "intent": "ai_service_error",
            "confidence": 1,
            "reason": "LLM service request failed",
        },
        "answer": answer,
        "service_province": request_data.service_province,
        "service_location_id": request_data.service_location_id,
        "service_address": request_data.service_address,
        "max_price": request_data.max_price,
        "latitude": request_data.latitude,
        "longitude": request_data.longitude,
        "max_distance_km": request_data.max_distance_km,
        "scheduled_start_time": request_data.scheduled_start_time,
        "scheduled_end_time": request_data.scheduled_end_time,
        "candidate_provider_ids": request_data.candidate_provider_ids,
        "tool_error": {
            "error": answer,
            "error_type": "llm_service_error",
        },
    }


@router.get("/ai/tasks")
def get_ai_tasks(
    task_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.AsyncTask)
    if current_user.role != "admin":
        query = query.filter(models.AsyncTask.user_id == current_user.id)
    if task_type:
        query = query.filter(models.AsyncTask.task_type == task_type)
    if status:
        query = query.filter(models.AsyncTask.status == status)
    query = query.order_by(models.AsyncTask.id.desc())
    async_tasks, total, page, page_size = paginate_query(query, page, page_size)
    result = [format_async_task_response(async_task) for async_task in async_tasks]
    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/ai/tasks/{task_id}")
def get_ai_task_status(
    task_id: str,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    async_task = (
        db.query(models.AsyncTask).filter(models.AsyncTask.task_id == task_id).first()
    )
    if not async_task:
        raise HTTPException(status_code=404, detail="Async task not found")
    if current_user.role != "admin" and async_task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot view this async task")
    task_result = AsyncResult(task_id, app=celery_app)
    async_task = sync_async_task_record_from_celery(async_task, task_result, db)
    return success_response(format_async_task_response(async_task))


@router.post("/ai/chat")
def enqueue_ai_chat(
    request_data: AIChatRequest,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    task = ai_chat_task.delay(current_user.id, request_data.model_dump())
    create_async_task_record(
        task.id, AsyncTaskType.ai_chat, db, user_id=current_user.id
    )
    return success_response({"task_id": task.id, "message": "AI chat task enqueued"})


@router.post("/ai/chat/async")
def enqueue_ai_chat_alias(
    request_data: AIChatRequest,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    return success_response(enqueue_ai_chat(request_data, current_user, db))


@router.post("/ai/chat/sync", response_model=ApiResponse[AIChatResponseData])
def ai_chat_sync(
    request_data: AIChatRequest,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    enforce_demo_ai_quota(current_user, db)
    try:
        result = handle_ai_chat_request(request_data, current_user, db)
    except Exception as error:
        if not is_llm_service_error(error):
            raise

        logger.warning("AI chat LLM service error: %s", error)
        result = build_ai_service_error_response(request_data, error, db)

    return success_response(result, message="AI chat completed")


@router.get("/ai/chat/messages")
def get_ai_chat_messages(
    page: int = 1,
    page_size: int = 50,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    expire_user_pending_actions(current_user.id, db)
    query = (
        db.query(models.AIChatMessage)
        .filter(models.AIChatMessage.user_id == current_user.id)
        .order_by(models.AIChatMessage.created_at.desc())
    )
    messages, total, page, page_size = paginate_query(query, page, page_size)
    messages.reverse()
    result = [format_ai_chat_message(message) for message in messages]
    sync_ai_action_statuses_in_chat_history(result, current_user.id, db)
    return success_response(build_paginated_response(result, total, page, page_size))


def sync_ai_action_statuses_in_chat_history(
    messages: list[dict],
    user_id: int,
    db: Session,
):
    """Overwrite card snapshot in chat with live pending-action status."""
    action_ids = {
        card.get("action_id")
        for message in messages
        if isinstance(message.get("metadata"), dict)
        for card in [message["metadata"].get("confirmation_card")]
        if isinstance(card, dict) and isinstance(card.get("action_id"), int)
    }
    if not action_ids:
        return

    actions = (
        db.query(models.AIPendingAction)
        .filter(
            models.AIPendingAction.user_id == user_id,
            models.AIPendingAction.id.in_(action_ids),
        )
        .all()
    )
    status_by_action_id = {action.id: action.status for action in actions}

    for message in messages:
        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            continue

        confirmation_card = metadata.get("confirmation_card")
        if not isinstance(confirmation_card, dict):
            continue

        action_id = confirmation_card.get("action_id")
        current_status = status_by_action_id.get(action_id)
        if current_status is None:
            continue

        confirmation_card["status"] = current_status
        pending_action = metadata.get("pending_action")
        if isinstance(pending_action, dict):
            pending_action["status"] = current_status


@router.delete("/ai/chat/messages")
def clear_ai_chat_messages(
    current_user: models.User = Depends(require_verified_user), db: Session = Depends(get_db)
):
    deleted_count = delete_ai_chat_messages(current_user.id, db)
    return success_response(
        {
            "deleted_count": deleted_count,
            "message": "AI chat messages deleted successfully",
        }
    )


@router.get("/ai/tools")
def get_ai_tools(
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    return success_response(get_langchain_tool_summaries(current_user, db))


@router.post("/ai/tools/run")
def run_ai_tool(
    request_data: AIToolExecuteRequest,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    return success_response(
        run_langchain_tool(
            request_data.tool_name,
            request_data.tool_args,
            current_user,
            db,
        )
    )


@router.post("/ai/tools/agent-preview")
def preview_ai_tool_agent(
    request_data: AIToolAgentPreviewRequest,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    enforce_demo_ai_quota(current_user, db)
    return success_response(
        choose_and_run_langchain_tools(
            request_data.message,
            current_user,
            db,
            request_data.context,
        )
    )


@router.get("/ai/tool-call-logs")
def get_ai_tool_call_logs(
    tool_name: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.AIToolCallLog)
    if current_user.role != "admin":
        query = query.filter(models.AIToolCallLog.user_id == current_user.id)
    if tool_name:
        query = query.filter(models.AIToolCallLog.tool_name == tool_name)
    if status:
        query = query.filter(models.AIToolCallLog.status == status)

    query = query.order_by(models.AIToolCallLog.id.desc())
    logs, total, page, page_size = paginate_query(query, page, page_size)
    result = [format_ai_tool_call_log(log) for log in logs]

    return success_response(build_paginated_response(result, total, page, page_size))


@router.get("/ai/actions")
def get_ai_pending_actions(
    status: AIPendingActionStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    expire_user_pending_actions(current_user.id, db)
    query = db.query(models.AIPendingAction).filter(
        models.AIPendingAction.user_id == current_user.id
    )
    if status:
        query = query.filter(models.AIPendingAction.status == status)
    query = query.order_by(models.AIPendingAction.created_at.desc())
    actions, total, page, page_size = paginate_query(query, page, page_size)
    result = [format_ai_pending_action(action, db) for action in actions]

    return success_response(build_paginated_response(result, total, page, page_size))


@router.put("/ai/actions/{action_id}/cancel")
def cancel_ai_action(
    action_id: int,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    pending_action = cancel_ai_pending_action(action_id, current_user, db)

    return success_response(
        {
            "action_id": action_id,
            "cancelled": True,
            "pending_action": pending_action,
        }
    )


@router.post("/ai/actions/confirm")
async def confirm_ai_action(
    request_data: AIActionConfirmRequest,
    request: Request,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    enforce_demo_ai_quota(current_user, db)
    action = get_confirmable_ai_pending_action(
        request_data.action_id,
        current_user,
        db,
    )
    payload = load_json(action.payload_json, {})

    try:
        action_type = AIActionType(action.action_type)
        if action_type == AIActionType.create_booking:
            booking_data = BookingCreate(**payload)
            result = await create_customer_booking_action(
                booking_data,
                current_user,
                db,
                attachments=None,
            )
        elif action_type == AIActionType.cancel_booking:
            result = await cancel_customer_booking_action(
                payload["booking_id"],
                current_user,
                db,
            )
        elif action_type == AIActionType.request_refund:
            result = await create_customer_refund_request_action(
                payload["booking_id"],
                payload["reason"],
                current_user,
                db,
            )
        elif action_type == AIActionType.pay_booking:
            result = await pay_customer_booking_action(
                payload["booking_id"],
                payload.get("payment_method", "iyzico_checkout"),
                current_user,
                db,
                idempotency_key=f"ai-action-{action.id}",
                frontend_return_url=payment_result_url_for_request(request),
            )
        elif action_type == AIActionType.reject_quote:
            result = await reject_customer_booking_quote_action(
                payload["booking_id"],
                payload["status_note"],
                current_user,
                db,
            )
        elif action_type == AIActionType.confirm_complete:
            result = await confirm_customer_booking_complete_action(
                payload["booking_id"],
                current_user,
                db,
            )
        elif action_type == AIActionType.reject_complete:
            result = await reject_customer_booking_complete_action(
                payload["booking_id"],
                payload["status_note"],
                current_user,
                db,
            )
        elif action_type == AIActionType.quote_booking:
            quote_data = ProviderBookingQuoteCreate(
                quote_amount=payload["quote_amount"],
                expected_service_amount=payload.get(
                    "expected_service_amount", payload["quote_amount"]
                ),
                visit_fee_amount=payload["visit_fee_amount"],
                quote_message=payload.get("quote_message"),
            )
            result = await quote_provider_booking_action(
                payload["booking_id"],
                quote_data,
                current_user,
                db,
            )
        elif action_type == AIActionType.reject_booking:
            note_data = BookingNoteUpdate(status_note=payload["status_note"])
            result = await reject_provider_booking_action(
                payload["booking_id"],
                note_data,
                current_user,
                db,
            )
        elif action_type == AIActionType.complete_booking:
            result = await complete_provider_booking_action(
                payload["booking_id"],
                current_user,
                db,
            )
        elif action_type == AIActionType.approve_refund:
            result = await approve_provider_refund_request_action(
                payload["refund_request_id"],
                current_user,
                db,
            )
        elif action_type == AIActionType.reject_refund:
            reject_data = ProviderRefundRejectCreate(
                provider_note=payload["provider_note"]
            )
            result = await reject_provider_refund_request_action(
                payload["refund_request_id"],
                reject_data,
                current_user,
                db,
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported AI action type")
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Missing action payload field: {exc.args[0]}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Unsupported AI action type"
        ) from exc

    pending_action = mark_ai_pending_action_executed(action, db)

    return success_response(
        {
            "action_id": action.id,
            "action_type": action.action_type,
            "executed": True,
            "pending_action": pending_action,
            "result": result,
        }
    )


@router.get("/ai/actions/{action_id}")
def get_ai_pending_action(
    action_id: int,
    current_user: models.User = Depends(require_verified_user),
    db: Session = Depends(get_db),
):
    action = get_ai_pending_action_or_404(action_id, current_user, db)
    action = refresh_ai_pending_action_expiration(action, db)

    return success_response(format_ai_pending_action(action, db))


@router.post("/ai/recommend-providers")
def recommend_providers(
    request_data: AIProviderRecommendRequest,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    parsed_need = parse_user_service_need(request_data.query)
    provider_search_result = search_providers_tool(
        query=request_data.query,
        service_tags=parsed_need["matched_tags"],
        service_province=request_data.service_province,
        service_location_id=request_data.service_location_id,
        max_price=request_data.max_price,
        budget_preference=parsed_need["budget_preference"],
        current_user=current_user,
        db=db,
        latitude=request_data.latitude,
        longitude=request_data.longitude,
        max_distance_km=request_data.max_distance_km,
        scheduled_start_time=request_data.scheduled_start_time,
        scheduled_end_time=request_data.scheduled_end_time,
        limit=None,
    )
    return success_response({"parsed_need": parsed_need, **provider_search_result})


@router.get("/ai/oauth")
def get_ai_oauth_status(current_user: models.User = Depends(require_admin)):
    return success_response(subscription_status())


@router.post("/ai/oauth/chatgpt/start")
def start_chatgpt_oauth(current_user: models.User = Depends(require_admin)):
    reject_demo_restricted_action(current_user, "start_chatgpt_oauth")
    try:
        chatgpt_oauth.start()
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return success_response(subscription_status())


@router.post("/ai/oauth/chatgpt/cancel")
def cancel_chatgpt_oauth(current_user: models.User = Depends(require_admin)):
    reject_demo_restricted_action(current_user, "cancel_chatgpt_oauth")
    chatgpt_oauth.cancel()
    return success_response(subscription_status())


@router.post("/ai/oauth/chatgpt/logout")
def logout_chatgpt_oauth(current_user: models.User = Depends(require_admin)):
    reject_demo_restricted_action(current_user, "logout_chatgpt_oauth")
    return success_response(logout_chatgpt())


@router.put("/ai/oauth")
def update_ai_oauth_auth(
    request_data: LLMAuthUpdate,
    current_user: models.User = Depends(require_admin),
):
    reject_demo_restricted_action(current_user, "update_ai_oauth_auth")
    try:
        set_saved_auth(request_data.auth, request_data.model)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return success_response(subscription_status())


@router.put("/ai/oauth/key")
def update_ai_oauth_key(
    request_data: LLMApiKeyUpdate,
    current_user: models.User = Depends(require_admin),
):
    reject_demo_restricted_action(current_user, "update_ai_oauth_key")
    try:
        save_admin_llm(
            request_data.provider,
            request_data.api_key,
            request_data.base_url,
            request_data.model,
        )
        set_saved_auth("key")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return success_response(subscription_status())


@router.delete("/ai/oauth/key")
def delete_ai_oauth_key(current_user: models.User = Depends(require_admin)):
    reject_demo_restricted_action(current_user, "delete_ai_oauth_key")
    clear_admin_llm()
    return success_response(subscription_status())


@router.post("/ai/oauth/models")
def list_ai_oauth_models(
    request_data: LLMModelsRequest,
    current_user: models.User = Depends(require_admin),
):
    reject_demo_restricted_action(current_user, "list_ai_oauth_models")
    try:
        if request_data.source in {"chatgpt", "grok"}:
            return success_response(list_subscription_models(request_data.source))
        return success_response(
            list_key_models(
                request_data.provider,
                request_data.api_key,
                request_data.base_url,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/ai/oauth/grok/start")
def start_grok_oauth(current_user: models.User = Depends(require_admin)):
    reject_demo_restricted_action(current_user, "start_grok_oauth")
    try:
        grok_oauth.start()
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return success_response(subscription_status())


@router.post("/ai/oauth/grok/cancel")
def cancel_grok_oauth(current_user: models.User = Depends(require_admin)):
    reject_demo_restricted_action(current_user, "cancel_grok_oauth")
    grok_oauth.cancel()
    return success_response(subscription_status())


@router.post("/ai/oauth/grok/logout")
def logout_grok_oauth(current_user: models.User = Depends(require_admin)):
    reject_demo_restricted_action(current_user, "logout_grok_oauth")
    return success_response(logout_grok())


@router.get("/ai/health/redis")
def check_ai_redis_health(current_user: models.User = Depends(require_admin)):
    return success_response({"redis": "ok" if check_redis_connection() else "error"})


@router.get("/ai/health/milvus")
def check_ai_milvus_health(current_user: models.User = Depends(require_admin)):
    server_version = check_milvus_connection()
    return success_response({"milvus": "ok", "server_version": server_version})


@router.get("/ai/health/qwen")
def check_ai_qwen_health(current_user: models.User = Depends(require_admin)):
    response = test_qwen_chat()
    return success_response({"qwen": "ok", "response": response})


@router.get("/ai/health/embedding")
def check_ai_embedding_health(current_user: models.User = Depends(require_admin)):
    embedding = generate_embedding("Kitchen pipe leak, needs on-site plumbing repair")
    return success_response(
        {"embedding": "ok", "dimension": len(embedding), "preview": embedding[:5]}
    )


@router.post("/ai/milvus/review-collection")
def create_ai_review_collection(current_user: models.User = Depends(require_admin)):
    return success_response(create_review_collection())


@router.post("/ai/milvus/sync-reviews")
def sync_reviews_to_milvus(
    current_user: models.User = Depends(require_admin), db: Session = Depends(get_db)
):
    task_id = enqueue_all_review_embeddings_sync(db, current_user.id)
    return success_response(
        {"task_id": task_id, "message": "Review embedding full sync enqueued"}
    )


@router.get("/ai/milvus/review-sync-status")
def get_review_sync_status(
    current_user: models.User = Depends(require_admin), db: Session = Depends(get_db)
):
    reviews = db.query(models.Review).all()
    result = {
        "total": len(reviews),
        "pending": 0,
        "synced": 0,
        "failed": 0,
        "deleted": 0,
        "unknown": 0,
    }
    for review in reviews:
        if review.embedding_status in result:
            result[review.embedding_status] += 1
        else:
            result["unknown"] += 1
    return success_response(result)


@router.post("/ai/milvus/retry-failed-reviews")
def retry_failed_review_embeddings(
    current_user: models.User = Depends(require_admin), db: Session = Depends(get_db)
):
    reviews = (
        db.query(models.Review)
        .filter(models.Review.embedding_status.in_(["failed", "pending"]))
        .all()
    )
    task_ids = []
    for review in reviews:
        task_ids.append(enqueue_review_embedding_sync(review, db, current_user.id))
    return success_response(
        {
            "review_count": len(reviews),
            "task_ids": task_ids,
            "message": "Failed or pending review embeddings enqueued for retry",
        }
    )
