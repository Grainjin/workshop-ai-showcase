"""Public demo journey on an Alembic-created PostgreSQL database, with real role tokens."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend import config, models
from backend.auth import get_db
from backend.constants import DEMO_USER_EMAILS
from backend.database import Base
from backend.main import app
from backend.reset_demo_data import reset_demo_database
from backend.routers import ai
from backend.seed_demo_data import seed_demo_data
from backend.utils import review_embedding_queue
from backend.utils.notification_queue import deliver_notification_task
from backend.utils.ai_pending_action import create_ai_pending_action
from backend.utils.demo_ai_quota import dispose_demo_ai_quota_engines
from test_demo_reset import owned_demo_engine  # noqa: F401
from test_demo_ai_routes import DISABLED, SUPPORTED
from tests.conftest import PNG_BYTES


def test_migrated_public_demo_role_journey(owned_demo_engine, monkeypatch):
    # Own a marker-named DB even when CI's suite database is workshop_test.
    engine = owned_demo_engine
    monkeypatch.setattr(config, "DEMO_MODE", True)
    monkeypatch.setattr(config, "PAYMENT_MODE", "demo")
    monkeypatch.setattr(config, "DEMO_AI_DAILY_LIMIT", 3)
    monkeypatch.setattr(config, "DEMO_AI_PER_MINUTE_LIMIT", 3)

    def forbidden(*args, **kwargs):
        raise AssertionError("Demo crossed an external payment, upload, embedding, or worker boundary")

    monkeypatch.setattr(Base.metadata, "create_all", forbidden)
    monkeypatch.setattr(Base.metadata, "drop_all", forbidden)
    monkeypatch.setattr("backend.services.iyzico.get_iyzico_client", forbidden)
    monkeypatch.setattr("backend.utils.provider_booking_actions.save_booking_attachment_upload", forbidden)
    monkeypatch.setattr("backend.ai.tools.generate_embedding", forbidden)
    monkeypatch.setattr("backend.ai.tools.search_review_embeddings", forbidden)
    for task in (review_embedding_queue.sync_review_embedding_task,
                 review_embedding_queue.delete_review_embedding_task,
                 review_embedding_queue.sync_all_review_embeddings_task, ai.ai_chat_task):
        monkeypatch.setattr(task, "delay", forbidden)
    notification_queue_calls = []
    def forbid_notification_queue(*args, **kwargs):
        notification_queue_calls.append((args, kwargs))
        forbidden()
    monkeypatch.setattr(deliver_notification_task, "apply_async", forbid_notification_queue)
    # Presence is optional in public V1, and must not depend on a Redis service.
    monkeypatch.setattr("backend.utils.formatters.is_user_online", lambda *_: False)

    def request_db():
        with Session(engine) as db:
            yield db

    def data(response, status=200):
        assert response.status_code == status, response.text
        return response.json()["data"]

    def booking_status(response, status):
        result = data(response)
        assert result["booking"]["status"] == status
        return result

    app.dependency_overrides[get_db] = request_db
    try:
        with Session(engine) as db:
            reset_demo_database(db, "reset-workshop-demo")
            seeded_task_count = db.query(models.AsyncTask).count()
            assert db.scalar(sa.text("SELECT version_num FROM alembic_version")) == "0019_demo_ai_usage"
            provider = db.query(models.ProviderProfile).join(models.User).filter(
                models.User.email == DEMO_USER_EMAILS["provider"]).one()
            provider_id, category = provider.id, provider.tags.split(",")[0]
            latitude, longitude = provider.latitude, provider.longitude
            payout = db.query(models.ProviderSubmerchant).filter_by(provider_profile_id=provider_id).one()
            assert payout.status == "active" and payout.submerchant_key is None and payout.iban is None
            assert all(row.status == "draft" for row in db.query(models.ProviderSubmerchant)
                       .filter(models.ProviderSubmerchant.id != payout.id))

        client = TestClient(app)
        roles = {}
        for role in ("customer", "provider", "admin"):
            login = data(client.post("/demo/login", json={"role": role}))
            headers = {"Authorization": "Bearer " + login["access_token"]}
            user = data(client.get("/me", headers=headers))
            assert user["email"] == DEMO_USER_EMAILS[role] and user["role"] == role
            assert login["refresh_token"]
            roles[role] = (headers, user["id"])
        customer, customer_id = roles["customer"]
        provider_headers, _ = roles["provider"]
        admin, _ = roles["admin"]
        verification = data(client.get("/provider/verification-status", headers=provider_headers))
        assert verification["identity_status"] == verification["qualification_status"] == "approved"
        assert data(client.get("/provider/submerchant", headers=provider_headers))["submerchant"]["status"] == "active"
        data(client.get("/provider/dashboard", headers=provider_headers))

        # A future weekday inside seeded operating hours, using the provider's real location.
        start = (datetime.now(timezone.utc) + timedelta(days=8)).replace(hour=10, minute=0, second=0, microsecond=0)
        while start.weekday() >= 5:
            start += timedelta(days=1)
        booking = data(client.post("/bookings", headers=customer, data={
            "provider_profile_id": provider_id, "service_category": category,
            "title": "Public demo service", "service_description": "Simulated repair journey",
            "service_address": "Demo Istanbul address", "service_latitude": latitude,
            "service_longitude": longitude, "scheduled_start_time": start.isoformat(),
            "scheduled_end_time": (start + timedelta(hours=1)).isoformat(),
        }))["booking"]
        booking_id = booking["id"]
        assert booking["status"] == "pending"
        booking_status(client.put(f"/provider/bookings/{booking_id}/quote", headers=provider_headers,
            json={"expected_service_amount": 500, "visit_fee_amount": 100}), "quoted")
        booking_status(client.put(f"/customer/bookings/{booking_id}/accept-quote", headers=customer),
            "awaiting_visit_payment")
        visit = booking_status(client.put(f"/customer/bookings/{booking_id}/pay", headers={
            **customer, "Idempotency-Key": "demo-journey-visit"},
            json={"payment_stage": "visit_fee"}), "visit_paid")
        assert visit["payment"]["payment_method"] == "demo" and visit["payment"]["checkout_url"] is None
        for action in ("start-visit", "complete"):
            response = client.put(f"/provider/bookings/{booking_id}/{action}", headers=provider_headers,
                files={"proof_files": ("arbitrary.png", PNG_BYTES, "image/png")})
            assert response.status_code == 403
            assert response.json()["error"]["detail"]["code"] == "DEMO_RESTRICTED_ACTION"
        booking_status(client.put(f"/provider/demo/bookings/{booking_id}/start-visit",
            headers=provider_headers), "provider_arrived")
        booking_status(client.put(f"/provider/demo/bookings/{booking_id}/start-visit",
            headers=provider_headers), "provider_arrived")
        booking_status(client.put(f"/provider/bookings/{booking_id}/final-quote", headers=provider_headers,
            json={"quote_amount": 500, "quote_message": "Simulated service quote"}), "final_quote_sent")
        booking_status(client.put(f"/customer/bookings/{booking_id}/accept-final-quote", headers=customer),
            "awaiting_service_payment")
        service = booking_status(client.put(f"/customer/bookings/{booking_id}/pay", headers={
            **customer, "Idempotency-Key": "demo-journey-service"},
            json={"payment_stage": "service_fee"}), "service_paid")
        assert service["payment"]["payment_method"] == "demo"
        booking_status(client.put(f"/provider/demo/bookings/{booking_id}/complete",
            headers=provider_headers), "awaiting_confirmation")
        with Session(engine) as db:
            proof_id = db.query(models.BookingAttachment).filter_by(
                booking_id=booking_id, purpose="completion_proof").one().id
            history_count = db.query(models.BookingStatusHistory).filter_by(booking_id=booking_id).count()
        booking_status(client.put(f"/provider/demo/bookings/{booking_id}/complete",
            headers=provider_headers), "awaiting_confirmation")
        with Session(engine) as db:
            assert db.query(models.BookingStatusHistory).filter_by(booking_id=booking_id).count() == history_count
        booking_status(client.put(f"/customer/bookings/{booking_id}/reject-complete", headers=customer,
            json={"status_note": "Please resubmit simulated completion proof"}), "accepted")
        booking_status(client.put(f"/provider/demo/bookings/{booking_id}/complete",
            headers=provider_headers), "awaiting_confirmation")
        with Session(engine) as db:
            assert db.query(models.BookingAttachment).filter_by(
                booking_id=booking_id, purpose="completion_proof").one().id == proof_id
            history_count = db.query(models.BookingStatusHistory).filter_by(booking_id=booking_id).count()
        booking_status(client.put(f"/provider/demo/bookings/{booking_id}/complete",
            headers=provider_headers), "awaiting_confirmation")
        with Session(engine) as db:
            assert db.query(models.BookingStatusHistory).filter_by(booking_id=booking_id).count() == history_count
        # Confirmation exercises real business execution and exactly one AI quota unit.
        with Session(engine) as db:
            action = create_ai_pending_action(customer_id, "confirm_complete", {"booking_id": booking_id},
                "Confirm demo completion", [], db)
        data(client.post("/ai/actions/confirm", headers=customer, json={"action_id": action["id"]}))
        with Session(engine) as db:
            assert db.get(models.Booking, booking_id).status == "completed"
            assert db.query(models.DemoAIUsage).one().daily_count == 1
        review = data(client.post(f"/bookings/{booking_id}/review", headers=customer,
            json={"rating": 5, "comment": "Simulated demo review"}))
        assert review["embedding_task_id"] is None
        notices = data(client.get("/notifications", headers=customer))
        assert notices["total"] > 0
        data(client.get("/admin/dashboard", headers=admin))
        blocked = client.put(f"/admin/users/{customer_id}/status", headers=admin, json={"is_banned": True})
        assert blocked.status_code == 403
        assert blocked.json()["error"]["detail"]["code"] == "DEMO_RESTRICTED_ACTION"

        # Exercise real sync orchestration with its expected unavailable-model fallback.
        sync = data(client.post("/ai/chat/sync", headers=customer, json={"message": "Hello"}))
        assert sync["answer"]
        # Replace only the model selection boundary; tools and quota remain real.
        def model_preview(message, user, db, context):
            from backend.ai.tools import summarize_provider_reviews_tool
            return summarize_provider_reviews_tool(message, [provider_id], user, db)
        monkeypatch.setattr(ai, "choose_and_run_langchain_tools", model_preview)
        preview = data(client.post("/ai/tools/agent-preview", headers=customer, json={"message": "Reviews"}))
        assert preview["review_context_source"] == "database"
        for path, payload in SUPPORTED:
            response = client.post(path, headers=customer, json=payload)
            assert response.status_code == 429, response.text
            assert response.json()["error"]["detail"]["code"] == "DEMO_AI_LIMIT_REACHED"
        for method, path in DISABLED:
            response = client.request(method, path, headers=customer, content=b"{broken")
            assert response.status_code == 404 and response.json()["error"]["detail"] == "Not found"
        with Session(engine) as db:
            assert db.query(models.DemoAIUsage).one().daily_count == 3
            assert db.query(models.AsyncTask).count() == seeded_task_count
            assert notification_queue_calls == []
            assert db.get(models.User, customer_id).is_banned is False
            proofs = db.query(models.BookingAttachment).filter_by(booking_id=booking_id).all()
            assert sorted(row.purpose for row in proofs) == ["arrival_evidence", "completion_proof"]
            for proof in proofs:
                asset = client.get(proof.file_url)
                assert asset.status_code == 200 and "Simulated demo proof" in asset.text
            payments = db.query(models.Payment).filter_by(booking_id=booking_id).all()
            assert len(payments) == 2 and all(row.external_status == "simulated" for row in payments)
            assert db.query(models.PaymentSettlement).filter_by(booking_id=booking_id).count() == 2
            # Rerun repairs drift; the guarded reset restores the mapped Provider too.
            payout = db.query(models.ProviderSubmerchant).filter_by(provider_profile_id=provider_id).one()
            payout.status, payout.submerchant_key = "rejected", "drift"
            db.commit()
            seed_demo_data(db)
            db.commit()
            assert payout.status == "active" and payout.submerchant_key is None
            db.rollback()
            reset_demo_database(db, "reset-workshop-demo")
            assert db.query(models.DemoAIUsage).count() == 0
            assert db.query(models.ProviderSubmerchant).filter_by(provider_profile_id=provider_id).one().status == "active"
        print("Demo journey: migrated 0019; three role logins/readiness; booking; visit payment; preset arrival; "
              "final quote; service payment; preset completion; AI confirmation; review; admin read/403; "
              "AI 3 units/3 blocked/13 hidden; two settlements; seed rerun/reset repaired; external boundaries blocked")
    finally:
        app.dependency_overrides.pop(get_db, None)
        dispose_demo_ai_quota_engines(engine)
