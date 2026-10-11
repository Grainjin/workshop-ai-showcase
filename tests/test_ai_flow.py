from backend.utils.ai_pending_action import create_ai_pending_action
from tests.conftest import create_booking
from backend import config, models
from backend.ai.tools import summarize_provider_reviews_tool
import pytest
from datetime import datetime, timezone


@pytest.fixture
def fixed_quota_clock(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 10, 12, 30, 20, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr("backend.utils.demo_ai_quota.datetime", FixedDateTime)


def test_ai_chat_sync_returns_service_error_without_key(client, marketplace):
    response = client.post(
        "/ai/chat/sync",
        json={"message": "I need a plumber in Istanbul"},
        headers=marketplace["customer"]["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["type"] == "ai_service_error" or body.get("intent", {}).get("intent") == "ai_service_error"


def test_ai_chat_sync_with_mocked_handler(client, marketplace, monkeypatch):
    monkeypatch.setattr(
        "backend.routers.ai.handle_ai_chat_request",
        lambda request_data, current_user, db: {
            "message": request_data.message,
            "type": "answer",
            "intent": {"intent": "search_providers", "confidence": 1, "reason": "test"},
            "answer": "Here are nearby plumbers.",
        },
    )
    response = client.post(
        "/ai/chat/sync",
        json={"message": "Find a plumber"},
        headers=marketplace["customer"]["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["answer"] == "Here are nearby plumbers."


def test_ai_pending_action_confirm_cancels_booking(client, marketplace, db_session):
    customer = marketplace["customer"]
    booking = create_booking(
        client, customer["headers"], marketplace["provider_profile"]["id"]
    )
    created = create_ai_pending_action(
        customer["user"]["id"],
        "cancel_booking",
        {"booking_id": booking["id"]},
        "Cancel this booking",
        [],
        db_session,
    )
    confirmed = client.post(
        "/ai/actions/confirm",
        json={"action_id": created["id"]},
        headers=customer["headers"],
    )
    assert confirmed.status_code == 200, confirmed.text
    detail = client.get(f"/bookings/{booking['id']}", headers=customer["headers"])
    assert detail.json()["data"]["status"] == "cancelled"


def test_ai_pending_action_can_be_cancelled(client, marketplace, db_session):
    customer = marketplace["customer"]
    booking = create_booking(
        client, customer["headers"], marketplace["provider_profile"]["id"]
    )
    created = create_ai_pending_action(
        customer["user"]["id"],
        "cancel_booking",
        {"booking_id": booking["id"]},
        "Cancel this booking",
        [],
        db_session,
    )
    cancelled = client.put(
        f"/ai/actions/{created['id']}/cancel",
        headers=customer["headers"],
    )
    assert cancelled.status_code == 200, cancelled.text
    detail = client.get(f"/bookings/{booking['id']}", headers=customer["headers"])
    assert detail.json()["data"]["status"] == "pending"


def test_admin_oauth_status(client, marketplace):
    response = client.get("/ai/oauth", headers=marketplace["admin"]["headers"])
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["auth"] in {"key", "chatgpt", "grok"}
    assert "chatgpt" in data
    assert "grok" in data
    assert any(item["id"] == "claude" for item in data["providers"])
    assert data["key"]["source"] in {"admin", "env", "none"}
    assert "api_key_preview" in data["key"]


def test_admin_can_save_and_clear_api_key(client, marketplace, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.ai.oauth.api_key.ADMIN_KEY_PATH",
        tmp_path / "llm_api.json",
    )
    headers = marketplace["admin"]["headers"]
    saved = client.put(
        "/ai/oauth/key",
        json={
            "provider": "qwen",
            "api_key": "sk-admin-test-key",
            "model": "qwen3.8-max",
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["auth"] == "key"
    assert data["key"]["source"] == "admin"
    assert data["key"]["provider"] == "qwen"
    assert data["key"]["api_key_preview"] == "sk-a…-key"
    assert "sk-admin-test-key" not in saved.text

    forbidden = client.put(
        "/ai/oauth/key",
        json={"provider": "qwen", "api_key": "sk-customer"},
        headers=marketplace["customer"]["headers"],
    )
    assert forbidden.status_code == 403

    cleared = client.delete("/ai/oauth/key", headers=headers)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["key"]["source"] != "admin"


def test_admin_redis_health_reports_status(client, marketplace, monkeypatch):
    monkeypatch.setattr("backend.routers.ai.check_redis_connection", lambda: True)
    response = client.get("/ai/health/redis", headers=marketplace["admin"]["headers"])
    assert response.status_code == 200
    assert response.json()["data"]["redis"] == "ok"


def test_admin_milvus_health_reports_status(client, marketplace, monkeypatch):
    monkeypatch.setattr("backend.routers.ai.check_milvus_connection", lambda: "2.4-test")
    response = client.get("/ai/health/milvus", headers=marketplace["admin"]["headers"])
    assert response.status_code == 200
    assert response.json()["data"]["milvus"] == "ok"


@pytest.mark.parametrize("daily,minute", [(1, 10), (10, 1)])
def test_demo_ai_requests_charge_once_and_block_before_execution(
    client, marketplace, db_session, monkeypatch, daily, minute, fixed_quota_clock
):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", daily)
    monkeypatch.setattr(config, "DEMO_AI_PER_MINUTE_LIMIT", minute)
    calls = []

    def answer(request_data, current_user, db):
        calls.append(current_user.id)
        # An internal tool invocation must not charge a second time.
        summarize_provider_reviews_tool("reviews", [], current_user, db)
        return {"message": request_data.message, "type": "answer", "answer": "Available",
                "intent": {"intent": "answer", "confidence": 1, "reason": "test"}}

    monkeypatch.setattr("backend.routers.ai.handle_ai_chat_request", answer)
    headers = marketplace["customer"]["headers"]
    response = client.post("/ai/chat/sync", json={"message": "Help"}, headers=headers)
    assert response.status_code == 200, response.text
    assert db_session.query(models.DemoAIUsage).one().daily_count == 1
    denied = client.post("/ai/chat/sync", json={"message": "Help"}, headers=headers)
    assert denied.status_code == 429, denied.text
    detail = denied.json()["error"]["detail"]
    assert detail["code"] == "DEMO_AI_LIMIT_REACHED"
    assert detail["remaining_daily"] == daily - 1
    assert 1 <= detail["retry_after_seconds"] <= (86400 if daily == 1 else 60)
    assert denied.headers["retry-after"] == str(detail["retry_after_seconds"])
    assert len(calls) == 1
    # Different forwarded addresses cannot bypass the authenticated subject quota.
    spoofed = client.post("/ai/chat/sync", json={"message": "Help"},
                          headers={**headers, "X-Forwarded-For": "198.51.100.1"})
    assert spoofed.status_code == 429
    assert client.get("/customer/bookings", headers=headers).status_code == 200


def test_demo_confirmation_charged_once_and_non_ai_flow_survives_limit(
    client, marketplace, db_session, monkeypatch, fixed_quota_clock
):
    customer = marketplace["customer"]
    booking = create_booking(client, customer["headers"], marketplace["provider_profile"]["id"])
    pending = create_ai_pending_action(customer["user"]["id"], "cancel_booking",
                                      {"booking_id": booking["id"]}, "Cancel", [], db_session)
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", 1)
    confirmed = client.post("/ai/actions/confirm", json={"action_id": pending["id"]}, headers=customer["headers"])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["executed"] is True
    assert db_session.query(models.DemoAIUsage).one().daily_count == 1
    second = create_booking(client, customer["headers"], marketplace["provider_profile"]["id"])
    pending2 = create_ai_pending_action(customer["user"]["id"], "cancel_booking",
                                       {"booking_id": second["id"]}, "Cancel", [], db_session)
    denied = client.post("/ai/actions/confirm", json={"action_id": pending2["id"]}, headers=customer["headers"])
    assert denied.status_code == 429
    assert denied.json()["error"]["detail"]["code"] == "DEMO_AI_LIMIT_REACHED"
    assert client.get(f"/bookings/{second['id']}", headers=customer["headers"]).json()["data"]["status"] == "pending"
    assert db_session.get(models.AIPendingAction, pending2["id"]).status == "pending"
    direct = client.put(f"/customer/bookings/{second['id']}/cancel", headers=customer["headers"])
    assert direct.status_code == 200, direct.text


def test_demo_ai_provider_failure_is_charged_and_non_ai_remains_available(
    client, marketplace, db_session, monkeypatch, fixed_quota_clock
):
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", 1)
    def unavailable(*args):
        raise RuntimeError("LLM API key is not configured")
    monkeypatch.setattr("backend.routers.ai.handle_ai_chat_request", unavailable)
    headers = marketplace["customer"]["headers"]
    response = client.post("/ai/chat/sync", json={"message": "Help"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["type"] == "ai_service_error"
    assert db_session.query(models.DemoAIUsage).one().daily_count == 1
    assert client.get("/customer/bookings", headers=headers).status_code == 200


def test_normal_ai_has_no_quota_rows(client, marketplace, db_session, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", 1)
    for _ in range(2):
        response = client.post("/ai/chat/sync", json={"message": "Hello"}, headers=marketplace["customer"]["headers"])
        assert response.status_code == 200
    assert db_session.query(models.DemoAIUsage).count() == 0


@pytest.mark.parametrize("demo,vector_mode,source", [
    (True, "forbidden", "database"), (False, "failure", "sqlite"),
    (False, "empty", "sqlite"), (False, "available", "milvus"),
])
def test_review_context_demo_skips_vectors_and_normal_preserves_fallback(
    client, marketplace, db_session, monkeypatch, demo, vector_mode, source
):
    customer = marketplace["customer"]
    provider_id = marketplace["provider_profile"]["id"]
    booking = create_booking(client, customer["headers"], provider_id)
    db_session.add(models.Review(booking_id=booking["id"], customer_id=customer["user"]["id"],
                                provider_profile_id=provider_id, rating=5, comment="Careful repair"))
    db_session.commit()
    monkeypatch.setattr(config, "DEMO_MODE", demo)
    calls = []
    def embedding(question):
        calls.append("embedding")
        if vector_mode == "failure":
            raise RuntimeError("Embeddings unavailable")
        return [0.1]
    def vectors(*args):
        calls.append("milvus")
        if vector_mode == "available":
            return [{"provider_id": provider_id, "positive_reviews": [{"comment": "Vector repair", "rating": 5}], "negative_reviews": []}]
        return []
    monkeypatch.setattr("backend.ai.tools.generate_embedding", embedding)
    monkeypatch.setattr("backend.ai.tools.search_review_embeddings", vectors)
    result = summarize_provider_reviews_tool("Quality?", [provider_id], db_session.get(models.User, customer["user"]["id"]), db_session)
    assert result["review_context_source"] == source
    expected = "Vector repair" if vector_mode == "available" else "Careful repair"
    assert result["review_context"][0]["positive_reviews"][0]["comment"] == expected
    if demo:
        assert calls == []
    else:
        assert calls[0] == "embedding"
