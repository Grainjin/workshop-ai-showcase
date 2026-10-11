"""Public readiness is DB availability plus redacted, optional AI configuration."""

import json

import pytest
from sqlalchemy.exc import OperationalError

from backend import config, database
from backend.ai.oauth import api_key, runtime


@pytest.fixture(autouse=True)
def isolate_ai_configuration(tmp_path, monkeypatch):
    monkeypatch.setattr(api_key, "ADMIN_KEY_PATH", tmp_path / "llm_api.json")
    monkeypatch.setattr(runtime, "_ACTIVE_PATH", tmp_path / "llm_auth.json")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "PAYMENT_MODE", "demo")


def test_ready_when_database_and_ai_key_are_configured(client, monkeypatch):
    # A false core status or exposing credentials instead of booleans breaks this contract.
    monkeypatch.setenv("LLM_API_KEY", "not-a-real-key")
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Success",
        "data": {
            "status": "ready", "ready": True, "database": "available",
            "demo_mode": True, "payment_mode": "demo", "ai_configured": True,
            "degraded_services": [],
        },
    }


def test_missing_ai_key_degrades_without_failing_core_readiness(client):
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["ready"] is True
    assert data["status"] == "degraded"
    assert data["database"] == "available"
    assert data["ai_configured"] is False
    assert data["degraded_services"] == ["ai"]
    # Anonymous core discovery still responds; readiness never becomes an AI gate.
    assert client.get("/providers").status_code == 200


def test_database_outage_returns_503_without_changing_liveness(client, monkeypatch):
    def unavailable():
        raise OperationalError(
            "SELECT 1", {}, Exception("postgresql://admin:password@private.example/db")
        )

    with monkeypatch.context() as outage:
        outage.setattr(database.engine, "connect", unavailable)
        response = client.get("/ready")
        assert client.get("/health").json() == {
            "success": True, "message": "Success",
            "data": {"status": "ok", "service": "Workshop AI backend"},
        }
    assert response.status_code == 503
    data = response.json()["data"]
    assert data["ready"] is False
    assert data["status"] == "not_ready"
    assert data["database"] == "unavailable"
    assert data["degraded_services"] == ["database", "ai"]
    assert "password" not in response.text
    assert "private.example" not in response.text


def test_readiness_reports_payment_and_demo_configuration(client, monkeypatch):
    monkeypatch.setattr(config, "DEMO_MODE", False)
    monkeypatch.setattr(config, "PAYMENT_MODE", "iyzico_sandbox")
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["data"]["demo_mode"] is False
    assert response.json()["data"]["payment_mode"] == "iyzico_sandbox"


def test_readiness_redacts_admin_keys_urls_and_other_secrets(client, monkeypatch):
    secrets = ["sk-private-admin-key", "private-vendor.example", "vendor-password",
               "db-password", "smtp-password", "iyzico-private-key"]
    api_key.ADMIN_KEY_PATH.write_text(json.dumps({
        "provider": "custom", "api_key": secrets[0],
        "base_url": f"https://user:{secrets[2]}@{secrets[1]}/v1", "model": "private-model",
    }))
    monkeypatch.setattr(config, "DATABASE_URL", f"postgresql://user:{secrets[3]}@db.example/private")
    monkeypatch.setattr(config, "SMTP_PASSWORD", secrets[4])
    monkeypatch.setattr(config, "IYZICO_API_KEY", secrets[5])
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["data"]["ai_configured"] is True
    for secret in [*secrets, "private-model", "db.example", "api_key_preview", "base_url"]:
        assert secret not in response.text


@pytest.mark.parametrize("auth_mode", ["chatgpt", "grok"])
def test_connected_selected_subscription_counts_as_configured(client, monkeypatch, auth_mode):
    runtime._ACTIVE_PATH.write_text(json.dumps({"auth": auth_mode}))
    monkeypatch.setattr(getattr(runtime, f"{auth_mode}_oauth"), "connected", lambda: True)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["data"]["ai_configured"] is True


def test_invalid_optional_ai_configuration_is_redacted_and_degraded(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "private-invalid-provider")
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["data"]["ai_configured"] is False
    assert "private-invalid-provider" not in response.text
