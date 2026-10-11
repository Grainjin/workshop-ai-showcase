from hashlib import sha256

import pytest
from fastapi import HTTPException
from jose import jwt

from backend import models
from backend.services import social_auth_service
from backend.services.social_auth_service import VerifiedSocialIdentity
from tests.conftest import _rsa_pem_pair, register_session

APPLE_AUD = "ai.workshop.app"


def fake_identity(monkeypatch, **overrides):
    fields = {
        "provider": "google",
        "provider_user_id": "sub-1",
        "email": "social@example.com",
        "name": "Sam Social",
        "given_name": "Sam",
        "family_name": "Social",
    }
    fields.update(overrides)
    seen = {}

    def verify(provider, token, nonce=None):
        seen["nonce"] = nonce
        return VerifiedSocialIdentity(**fields)

    monkeypatch.setattr("backend.routers.auth.verify_social_identity", verify)
    return seen


def social_login(client, **body):
    payload = {"provider": "google", "id_token": "fake-token"}
    payload.update(body)
    return client.post("/social-login", json=payload)


def test_new_account_needs_terms_and_creates_nothing_without_them(client, db_session, monkeypatch):
    fake_identity(monkeypatch)

    response = social_login(client)

    assert response.status_code == 409
    assert "terms" in response.json()["message"].lower()
    assert db_session.query(models.User).filter_by(email="social@example.com").first() is None


def test_provider_sign_up_starts_both_verifications_as_not_submitted(client, monkeypatch):
    fake_identity(monkeypatch)

    response = social_login(client, role="provider", tos_accepted=True)

    assert response.status_code == 200, response.text
    user = response.json()["data"]["user"]
    assert user["role"] == "provider"
    assert user["identity_verification_status"] == "not_submitted"
    assert user["qualification_verification_status"] == "not_submitted"
    assert user["email_verified"] is True


def test_token_without_verified_email_cannot_create_or_claim_an_account(client, monkeypatch):
    register_session(client, "victim@example.com")
    fake_identity(monkeypatch, email=None)

    # The app may not name the address itself; the field is ignored.
    response = social_login(client, tos_accepted=True, email="victim@example.com")

    assert response.status_code == 400
    assert "verified email" in response.json()["message"].lower()


def test_verified_email_links_existing_password_account(client, db_session, monkeypatch):
    existing = register_session(client, "linked@example.com", verified=False)
    fake_identity(monkeypatch, email="linked@example.com")

    response = social_login(client)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["is_new_user"] is False
    assert data["linked_social_account"] is True
    assert data["user"]["id"] == existing["user"]["id"]
    # The provider vouched for the address, so the old account is now verified.
    assert data["user"]["email_verified"] is True


def test_repeat_sign_in_uses_the_link_even_when_apple_omits_the_email(client, monkeypatch):
    fake_identity(monkeypatch, provider="apple", provider_user_id="apple-sub")
    first = social_login(client, provider="apple", nonce="n", tos_accepted=True)
    assert first.status_code == 200, first.text

    fake_identity(monkeypatch, provider="apple", provider_user_id="apple-sub", email=None)
    again = social_login(client, provider="apple", nonce="n")

    assert again.status_code == 200, again.text
    assert again.json()["data"]["is_new_user"] is False
    assert again.json()["data"]["user"]["id"] == first.json()["data"]["user"]["id"]


def test_apple_names_come_from_the_app(client, monkeypatch):
    seen = fake_identity(
        monkeypatch,
        provider="apple",
        name=None,
        given_name=None,
        family_name=None,
    )

    response = social_login(
        client,
        provider="apple",
        nonce="raw-nonce",
        tos_accepted=True,
        first_name="Ada",
        last_name="Lovelace",
    )

    assert response.status_code == 200, response.text
    user = response.json()["data"]["user"]
    assert (user["first_name"], user["last_name"], user["name"]) == ("Ada", "Lovelace", "Ada Lovelace")
    assert seen["nonce"] == "raw-nonce"


def test_name_falls_back_to_the_email_local_part(client, monkeypatch):
    fake_identity(monkeypatch, name=None, given_name=None, family_name=None)

    response = social_login(client, tos_accepted=True)

    assert response.status_code == 200, response.text
    assert response.json()["data"]["user"]["name"] == "social"


# Token checks in the service itself.


@pytest.fixture
def apple_keys(monkeypatch):
    private_pem, public_pem = _rsa_pem_pair()
    monkeypatch.setattr(social_auth_service, "APPLE_CLIENT_IDS", [APPLE_AUD])
    monkeypatch.setattr(social_auth_service, "find_apple_signing_key", lambda key_id: public_pem)
    return private_pem


def apple_token(private_pem, **claims):
    payload = {
        "iss": "https://appleid.apple.com",
        "aud": APPLE_AUD,
        "sub": "apple-user",
        "email": "me@privaterelay.appleid.com",
        "email_verified": "true",
        "nonce": sha256(b"raw-nonce").hexdigest(),
        "exp": 4_102_444_800,
    }
    payload.update(claims)
    return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": "test"})


def test_apple_token_with_matching_nonce_is_accepted(apple_keys):
    identity = social_auth_service.verify_apple_identity(apple_token(apple_keys), "raw-nonce")

    assert identity.provider_user_id == "apple-user"
    assert identity.email == "me@privaterelay.appleid.com"


@pytest.mark.parametrize("nonce, status", [(None, 400), ("other-nonce", 401)])
def test_apple_token_needs_its_own_nonce(apple_keys, nonce, status):
    with pytest.raises(HTTPException) as error:
        social_auth_service.verify_apple_identity(apple_token(apple_keys), nonce)

    assert error.value.status_code == status


def test_apple_unverified_email_is_dropped(apple_keys):
    token = apple_token(apple_keys, email_verified="false")

    identity = social_auth_service.verify_apple_identity(token, "raw-nonce")

    assert identity.email is None


def test_apple_token_for_another_app_is_rejected(apple_keys):
    with pytest.raises(HTTPException) as error:
        social_auth_service.verify_apple_identity(
            apple_token(apple_keys, aud="com.other.app"),
            "raw-nonce",
        )

    assert error.value.status_code == 401


def google_payload(**claims):
    payload = {
        "iss": "https://accounts.google.com",
        "aud": "web-client",
        "sub": "google-user",
        "email": "me@gmail.com",
        "email_verified": True,
        "name": "Me Person",
        "given_name": "Me",
        "family_name": "Person",
        "nonce": "raw-nonce",
    }
    payload.update(claims)
    return payload


@pytest.fixture
def google_verifier(monkeypatch):
    from google.oauth2 import id_token as google_id_token

    monkeypatch.setattr(social_auth_service, "GOOGLE_CLIENT_IDS", ["web-client"])
    state = {"payload": google_payload()}
    monkeypatch.setattr(
        google_id_token,
        "verify_oauth2_token",
        lambda token, request, audience=None: state["payload"],
    )
    return state


def test_google_token_returns_split_names(google_verifier):
    identity = social_auth_service.verify_google_identity("token", "raw-nonce")

    assert (identity.given_name, identity.family_name) == ("Me", "Person")


def test_google_nonce_must_match_when_sent(google_verifier):
    with pytest.raises(HTTPException) as error:
        social_auth_service.verify_google_identity("token", "other-nonce")

    assert error.value.status_code == 401


def test_google_token_for_another_client_is_rejected(google_verifier):
    google_verifier["payload"] = google_payload(aud="someone-else")

    with pytest.raises(HTTPException) as error:
        social_auth_service.verify_google_identity("token")

    assert error.value.status_code == 401
