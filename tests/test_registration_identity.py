from datetime import datetime

import pytest

from backend import models
from backend.auth import create_password_identity
from backend.constants import DEMO_PASSWORD
from backend.services.social_auth_service import VerifiedSocialIdentity
from backend.utils.formatters import format_user_response
from tests.conftest import login, register_email_code, register_session


def registration_payload(role="customer"):
    return {
        "first_name": "  McKenna  ",
        "last_name": "  de Souza  ",
        "email": f"{role}-registration@example.com",
        "password": DEMO_PASSWORD,
        "confirm_password": DEMO_PASSWORD,
        "tos_accepted": True,
        "role": role,
        "email_code": "123456",
    }


@pytest.mark.parametrize("role", ["customer", "provider"])
def test_register_persists_split_name_and_server_terms_time(client, db_session, role):
    payload = registration_payload(role)
    payload["email_code"] = register_email_code(client, payload["email"])
    response = client.post("/register", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()["data"]["user"]
    assert (data["first_name"], data["last_name"], data["name"]) == (
        "McKenna",
        "de Souza",
        "McKenna de Souza",
    )
    assert datetime.fromisoformat(data["tos_accepted_at"])

    user = db_session.query(models.User).filter_by(email=f"{role}-registration@example.com").one()
    assert (user.first_name, user.last_name, user.name) == (
        "McKenna",
        "de Souza",
        "McKenna de Souza",
    )
    assert user.tos_accepted_at is not None
    assert not hasattr(user, "confirm_password")
    assert login(client, user.email).status_code == 200


@pytest.mark.parametrize(
    "change",
    [
        {"confirm_password": "OtherPassword123"},
        {"tos_accepted": False},
        {"confirm_password": None},
        {"tos_accepted": None},
        {"first_name": "  "},
        {"last_name": "  "},
    ],
)
def test_register_rejects_invalid_required_fields(client, change):
    payload = registration_payload()
    payload.update(change)
    response = client.post("/register", json=payload)
    assert response.status_code == 422, response.text


def test_register_rejects_missing_confirmation_and_terms(client):
    payload = registration_payload()
    del payload["confirm_password"]
    del payload["tos_accepted"]
    assert client.post("/register", json=payload).status_code == 422


def test_legacy_name_only_user_can_login_and_get_profile(client, db_session):
    user = models.User(name="Legacy Display", email="legacy-registration@example.com", role="customer")
    db_session.add(user)
    db_session.flush()
    create_password_identity(user, DEMO_PASSWORD, db_session)
    db_session.commit()
    session = login(client, user.email).json()["data"]
    response = client.get("/me", headers={"Authorization": f"Bearer {session['access_token']}"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["name"] == "Legacy Display"
    assert response.json()["data"]["first_name"] is None
    assert response.json()["data"]["last_name"] is None
    assert response.json()["data"]["tos_accepted_at"] is None


def test_social_sign_up_stores_split_names_and_terms(client, monkeypatch):
    monkeypatch.setattr(
        "backend.routers.auth.verify_social_identity",
        lambda provider, token, nonce=None: VerifiedSocialIdentity(
            provider="google",
            provider_user_id="registration-social-sub",
            email="social-registration@example.com",
            name="Social Person",
            given_name="Social",
            family_name="Person",
        ),
    )
    response = client.post(
        "/social-login",
        json={"provider": "google", "id_token": "fake-token", "tos_accepted": True},
    )
    assert response.status_code == 200, response.text
    user = response.json()["data"]["user"]
    assert user["name"] == "Social Person"
    assert user["first_name"] == "Social"
    assert user["last_name"] == "Person"
    assert user["tos_accepted_at"] is not None


@pytest.mark.parametrize("role", ["customer", "provider"])
def test_profile_single_field_patch_keeps_display_name_in_sync(client, db_session, role):
    session = register_session(client, f"{role}-patch-registration@example.com", role=role)
    response = client.patch("/me", json={"first_name": "  Öykü  "}, headers=session["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["data"]["name"] == "Öykü User"
    assert response.json()["data"]["last_name"] == "User"

    response = client.patch("/me", json={"last_name": "  McArthur  "}, headers=session["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["data"]["name"] == "Öykü McArthur"
    user = db_session.get(models.User, session["user"]["id"])
    db_session.refresh(user)
    assert user.name == "Öykü McArthur"


def test_legacy_name_patch_does_not_leave_stale_split_fields(client):
    session = register_session(client, "legacy-patch-registration@example.com")
    response = client.patch("/me", json={"name": "Only Display"}, headers=session["headers"])
    assert response.status_code == 200, response.text
    assert response.json()["data"]["name"] == "Only Display"
    assert response.json()["data"]["first_name"] is None
    assert response.json()["data"]["last_name"] is None
    assert (
        client.patch("/me", json={"first_name": "Alone"}, headers=session["headers"]).status_code
        == 422
    )


def test_split_name_patch_rejects_conflicting_name_source(client):
    session = register_session(client, "mixed-patch-registration@example.com")
    assert (
        client.patch(
            "/me", json={"name": "Display", "first_name": "First"}, headers=session["headers"]
        ).status_code
        == 422
    )


def test_chat_and_booking_consumers_read_synced_display_name(client, db_session):
    customer = register_session(client, "display-consumer-registration@example.com", name="Ayla Customer")
    changed = client.patch("/me", json={"first_name": "Ayla-Updated"}, headers=customer["headers"])
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["name"] == "Ayla-Updated Customer"

    user = db_session.get(models.User, customer["user"]["id"])
    formatted = format_user_response(user)
    assert formatted["name"] == "Ayla-Updated Customer"
    assert formatted["first_name"] == "Ayla-Updated"
    assert formatted["last_name"] == "Customer"


def test_openapi_contract_requires_registration_confirmation_and_terms(client):
    document = client.app.openapi()
    register = document["components"]["schemas"]["UserRegister"]
    assert {"first_name", "last_name", "confirm_password", "tos_accepted"} <= set(
        register["required"]
    )
    assert "tos_accepted_at" in document["components"]["schemas"]["UserResponse"]["properties"]
    assert "first_name" in document["components"]["schemas"]["UserProfilePatch"]["properties"]
    assert "last_name" in document["components"]["schemas"]["UserProfilePatch"]["properties"]
