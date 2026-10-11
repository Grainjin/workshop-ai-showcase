"""Every public AI cost entry point has an explicit demo policy."""

import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

from backend import config, models
from backend.auth import get_db, require_verified_user, require_admin
from backend.main import app
from backend.routers import ai
from backend.utils.demo_ai_quota import enforce_demo_ai_quota
from backend.utils import review_embedding_queue


DISABLED = [
    ("POST", "/ai/chat"), ("POST", "/ai/chat/async"),
    ("POST", "/ai/recommend-providers"),
    ("GET", "/ai/tasks"), ("GET", "/ai/tasks/not-a-task"),
    ("GET", "/ai/health/qwen"), ("GET", "/ai/health/embedding"),
    ("GET", "/ai/health/redis"), ("GET", "/ai/health/milvus"),
    ("POST", "/ai/milvus/review-collection"),
    ("POST", "/ai/milvus/sync-reviews"),
    ("POST", "/ai/milvus/retry-failed-reviews"),
    ("GET", "/ai/milvus/review-sync-status"),
]
SUPPORTED = [
    ("/ai/chat/sync", {"message": "Help"}),
    ("/ai/actions/confirm", {"action_id": 999}),
    ("/ai/tools/agent-preview", {"message": "Help", "context": {}}),
]


@pytest.mark.parametrize("path", ["/ai/chat", "/ai/chat/async"])
def test_normal_legacy_chat_still_enqueues(client, marketplace, db_session, monkeypatch, path):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(ai.ai_chat_task, "delay", lambda *_: SimpleNamespace(id="normal-chat-task"))
    response = client.post(path, json={"message": "Help"}, headers=marketplace["customer"]["headers"])
    assert response.status_code == 200, response.text
    task = db_session.query(models.AsyncTask).one()
    assert task.task_id == "normal-chat-task"
    assert task.user_id == marketplace["customer"]["user"]["id"]
    assert db_session.query(models.DemoAIUsage).count() == 0


def test_normal_qwen_diagnostic_retains_vendor_boundary(client, marketplace, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(ai, "test_qwen_chat", lambda: "Model available")
    response = client.get("/ai/health/qwen", headers=marketplace["admin"]["headers"])
    assert response.status_code == 200
    assert response.json()["data"] == {"qwen": "ok", "response": "Model available"}


@pytest.mark.parametrize("method,path", DISABLED)
@pytest.mark.parametrize("body", [b"", b"{broken", b'{"message":"Help"}'])
def test_disabled_ai_routes_hide_before_body_dependencies_or_external_work(monkeypatch, method, path, body):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    def forbidden(*args, **kwargs):
        pytest.fail("Disabled route reached a dependency or external/queue boundary")
    for dep in (get_db, require_verified_user, require_admin):
        app.dependency_overrides[dep] = forbidden
    for name in ("test_qwen_chat", "generate_embedding", "parse_user_service_need",
                 "enqueue_all_review_embeddings_sync", "enqueue_review_embedding_sync",
                 "check_redis_connection", "check_milvus_connection", "create_review_collection"):
        monkeypatch.setattr(ai, name, forbidden)
    monkeypatch.setattr(ai.ai_chat_task, "delay", forbidden)
    try:
        response = TestClient(app).request(method, path, content=body,
            headers={"Content-Type": "application/json"})
        assert response.status_code == 404, response.text
        assert response.json()["error"]["detail"] == "Not found"
    finally:
        for dep in (get_db, require_verified_user, require_admin):
            app.dependency_overrides.pop(dep, None)


@pytest.mark.parametrize("path,payload", SUPPORTED)
def test_exhausted_quota_blocks_all_supported_cost_routes(client, marketplace, db_session, monkeypatch, path, payload):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", 1)
    user = db_session.get(models.User, marketplace["customer"]["user"]["id"])
    enforce_demo_ai_quota(user, db_session)
    def forbidden(*args, **kwargs):
        pytest.fail("Exhausted quota reached model or business execution")
    for name in ("handle_ai_chat_request", "choose_and_run_langchain_tools", "get_confirmable_ai_pending_action"):
        monkeypatch.setattr(ai, name, forbidden)
    response = client.post(path, json=payload, headers=marketplace["customer"]["headers"])
    assert response.status_code == 429, response.text
    assert response.json()["error"]["detail"]["code"] == "DEMO_AI_LIMIT_REACHED"
    assert db_session.query(models.DemoAIUsage).one().daily_count == 1


def test_preview_charges_once_before_model_and_internal_tools(client, marketplace, db_session, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    def model_boundary(message, user, db, context):
        from backend.ai.tools import summarize_provider_reviews_tool
        result = summarize_provider_reviews_tool("Reviews", [], user, db)
        return {"answer": message, "source": result["review_context_source"]}
    monkeypatch.setattr(ai, "choose_and_run_langchain_tools", model_boundary)
    response = client.post("/ai/tools/agent-preview", json={"message": "Help"},
                           headers=marketplace["customer"]["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["data"]["source"] == "database"
    assert db_session.query(models.DemoAIUsage).one().daily_count == 1


@pytest.mark.parametrize("operation", ["sync", "delete"])
def test_demo_review_mutations_never_enqueue_embeddings(db_session, monkeypatch, operation):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    def forbidden(*args, **kwargs):
        pytest.fail("Demo review reached persistent worker queue")
    monkeypatch.setattr(review_embedding_queue.sync_review_embedding_task, "delay", forbidden)
    monkeypatch.setattr(review_embedding_queue.delete_review_embedding_task, "delay", forbidden)
    # No row is required: demo must return before marking/committing or enqueueing.
    review = models.Review(id=123, embedding_status="pending")
    assert getattr(review_embedding_queue, f"enqueue_review_embedding_{operation}")(review, db_session) is None
    assert db_session.query(models.AsyncTask).count() == 0
