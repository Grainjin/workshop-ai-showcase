import pytest

from backend import models
from backend.auth import create_password_identity, decode_token, get_password_identity
from backend.constants import DEMO_PASSWORD
from tests.conftest import create_admin_session, login, register, register_session
from backend.services.social_auth_service import VerifiedSocialIdentity


def test_register_rejects_admin_role(client):
    response = register(client, email="admin@example.com", role="admin")
    assert response.status_code == 400
    assert "admin" in response.json()["message"].lower()


def test_register_rejects_weak_password(client):
    response = register(client, email="weak@example.com", password="weakpass")
    assert response.status_code == 400
    assert "password" in response.json()["message"].lower() or "upper" in response.json()[
        "message"
    ].lower()


def test_register_and_login(client):
    created = register(client)
    assert created.status_code == 200
    assert created.json()["success"] is True
    assert created.json()["data"]["user"]["email"] == "customer@example.com"
    assert created.json()["data"]["user"]["role"] == "customer"
    # The sign-up code proved the address, so the account starts verified.
    assert created.json()["data"]["user"]["email_verified"] is True
    assert created.json()["data"]["user"]["phone_verified"] is False

    session = login(client)
    assert session.status_code == 200
    data = session.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"

    me = client.get("/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200
    assert me.json()["data"]["email"] == "customer@example.com"
    assert me.json()["data"]["email_verified"] is True
    assert me.json()["data"]["phone_verified"] is False


def test_duplicate_register_is_rejected(client):
    assert register(client).status_code == 200
    again = register(client)
    assert again.status_code == 400


def test_register_and_login_ignore_email_case(client):
    created = register(client, email="Case.User@Example.COM")
    assert created.status_code == 200
    assert created.json()["data"]["user"]["email"] == "case.user@example.com"

    session = login(client, email="CASE.USER@example.com")
    assert session.status_code == 200

    again = register(client, email="case.user@EXAMPLE.com")
    assert again.status_code == 400


def test_logout_revokes_access_token(client):
    register(client)
    session = login(client).json()["data"]
    access = session["access_token"]
    refresh = session["refresh_token"]

    logged_out = client.post("/logout", json={"refresh_token": refresh})
    assert logged_out.status_code == 200

    me = client.get("/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 401


def test_logout_revokes_refresh_token(client):
    register(client)
    session = login(client).json()["data"]
    refresh = session["refresh_token"]

    assert client.post("/logout", json={"refresh_token": refresh}).status_code == 200
    again = client.post("/refresh-token", json={"refresh_token": refresh})
    assert again.status_code == 401


def test_refresh_token_issues_new_pair(client):
    register(client)
    session = login(client).json()["data"]
    refreshed = client.post(
        "/refresh-token", json={"refresh_token": session["refresh_token"]}
    )
    assert refreshed.status_code == 200
    data = refreshed.json()["data"]
    assert data["access_token"]
    assert data["refresh_token"] != session["refresh_token"]

    me = client.get("/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200


def test_social_login_creates_customer(client, monkeypatch):
    monkeypatch.setattr(
        "backend.routers.auth.verify_social_identity",
        lambda provider, token, nonce=None: VerifiedSocialIdentity(
            provider="google",
            provider_user_id="google-sub-1",
            email="google.user@example.com",
            name="Google User",
        ),
    )
    response = client.post(
        "/social-login",
        json={
            "provider": "google",
            "id_token": "fake-token",
            "role": "customer",
            "tos_accepted": True,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["is_new_user"] is True
    assert data["user"]["email"] == "google.user@example.com"
    assert data["user"]["email_verified"] is True
    assert data["access_token"]


def test_admin_can_ban_user(client, db_session):
    admin = create_admin_session(client, db_session)
    customer = register_session(client, "banned@example.com", role="customer")
    user_id = customer["user"]["id"]

    banned = client.put(
        f"/admin/users/{user_id}/status",
        json={"is_banned": True},
        headers=admin["headers"],
    )
    assert banned.status_code == 200, banned.text

    blocked = login(client, "banned@example.com")
    assert blocked.status_code == 403


DEMO_ACCOUNTS = [
    ("customer", "demo_customer_1@workshop.ai"),
    ("provider", "demo_provider_1@workshop.ai"),
    ("admin", "demo_admin@workshop.ai"),
]


@pytest.fixture
def demo_users(db_session):
    users = {}
    for role, email in DEMO_ACCOUNTS:
        user = models.User(name=f"Demo {role}", email=email, role=role)
        db_session.add(user)
        db_session.flush()
        create_password_identity(user, DEMO_PASSWORD, db_session, verified=True)
        users[role] = user
    db_session.commit()
    return users


@pytest.mark.parametrize("body", [{"role": "customer"}, {"role": "unknown"}, {}])
def test_demo_login_disabled_is_generic_404(client, db_session, demo_users, monkeypatch, body):
    monkeypatch.setattr("backend.config.DEMO_MODE", False)
    response = client.post("/demo/login", json=body)
    assert response.status_code == 404
    assert response.json()["message"] == "Not found"
    assert "demo_" not in response.text
    assert "token" not in response.text
    assert db_session.query(models.RefreshToken).count() == 0


@pytest.mark.parametrize("enabled,expected_status", [(False, 404), (True, 422)])
@pytest.mark.parametrize(
    "content_type,body",
    [
        ("application/json", b'{"role":'),
        ("application/json; charset=utf-8", b'{"role":'),
        ("application/vnd.workshop+json", b'{"role":'),
        ("text/plain", b'{"role":'),
        ("application/x-www-form-urlencoded", b"role=customer"),
        ("multipart/form-data; boundary=demo", b'{"role":'),
    ],
)
def test_demo_login_gate_precedes_body_parsing(
    client, db_session, monkeypatch, enabled, expected_status, content_type, body
):
    monkeypatch.setattr("backend.config.DEMO_MODE", enabled)
    response = client.post("/demo/login", content=body, headers={"Content-Type": content_type})
    assert response.status_code == expected_status, response.text
    if not enabled:
        assert response.json()["message"] == "Not found"
        assert "role" not in response.text
        assert "demo_" not in response.text
        assert "token" not in response.text
    assert db_session.query(models.RefreshToken).count() == 0


def test_demo_login_rejects_unknown_role(client, monkeypatch):
    monkeypatch.setattr("backend.config.DEMO_MODE", True)
    response = client.post("/demo/login", json={"role": "superuser"})
    assert response.status_code == 422


@pytest.mark.parametrize("field", ["email", "password"])
def test_demo_login_rejects_client_credentials(client, demo_users, monkeypatch, field):
    monkeypatch.setattr("backend.config.DEMO_MODE", True)
    response = client.post("/demo/login", json={"role": "customer", field: "supplied"})
    assert response.status_code == 422


@pytest.mark.parametrize("role,email", DEMO_ACCOUNTS)
def test_demo_login_selects_stable_identity_and_normal_session(
    client, db_session, demo_users, monkeypatch, role, email
):
    monkeypatch.setattr("backend.config.DEMO_MODE", True)
    # A different account in the same role must never become the demo identity.
    db_session.add(models.User(name="Other account", email=f"other-{role}@example.com", role=role))
    db_session.commit()
    response = client.post("/demo/login", json={"role": role})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert set(data) == {"access_token", "refresh_token", "token_type", "user"}
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == email
    assert data["user"]["role"] == role
    assert data["user"]["id"] == demo_users[role].id
    assert data["user"]["email_verified"] is True
    assert data["user"]["last_login_at"]
    access = decode_token(data["access_token"])
    refresh = decode_token(data["refresh_token"])
    # Ordinary password login is disabled on the public demo; compare its normal-mode claims.
    monkeypatch.setattr("backend.config.DEMO_MODE", False)
    normal = login(client, email=email).json()["data"]
    monkeypatch.setattr("backend.config.DEMO_MODE", True)
    for token_type, claims in [("access", access), ("refresh", refresh)]:
        normal_claims = decode_token(normal[f"{token_type}_token"])
        assert set(claims) == set(normal_claims)
        assert claims["type"] == token_type
        assert claims["sub"] == str(demo_users[role].id)
        assert claims["role"] == role
        assert claims["exp"] - claims["iat"] == normal_claims["exp"] - normal_claims["iat"]
    assert access["sid"] == refresh["jti"]
    assert client.get("/me", headers={"Authorization": f"Bearer {data['access_token']}"}).json()[
        "data"
    ]["email"] == email
    refreshed = client.post("/refresh-token", json={"refresh_token": data["refresh_token"]})
    assert refreshed.status_code == 200
    rotated = refreshed.json()["data"]
    assert rotated["user"]["id"] == demo_users[role].id
    assert rotated["refresh_token"] != data["refresh_token"]
    reused = client.post("/refresh-token", json={"refresh_token": data["refresh_token"]})
    assert reused.status_code == 401
    assert client.post("/logout", json={"refresh_token": rotated["refresh_token"]}).status_code == 200
    logged_out = client.get("/me", headers={"Authorization": f"Bearer {rotated['access_token']}"})
    assert logged_out.status_code == 401
    revoked = client.post("/refresh-token", json={"refresh_token": rotated["refresh_token"]})
    assert revoked.status_code == 401


@pytest.mark.parametrize("role,email", DEMO_ACCOUNTS)
@pytest.mark.parametrize("invalid", ["missing", "wrong_role", "inactive", "banned", "unverified"])
def test_demo_login_unavailable_identity_never_issues_token(
    client, db_session, demo_users, monkeypatch, role, email, invalid
):
    monkeypatch.setattr("backend.config.DEMO_MODE", True)
    user = demo_users[role]
    if invalid == "missing":
        # Leave other same-role accounts present to catch fallback selection.
        user.email = f"unmapped-{role}@example.com"
    elif invalid == "wrong_role":
        user.role = "customer" if role != "customer" else "admin"
    elif invalid == "inactive":
        user.is_active = False
    elif invalid == "banned":
        user.is_banned = True
    else:
        user.email_verified_at = None
    db_session.commit()
    response = client.post("/demo/login", json={"role": role})
    assert response.status_code == 503
    assert response.json()["message"] == "Demo login is unavailable"
    assert email not in response.text
    assert role not in response.text
    assert "token" not in response.text
    assert db_session.query(models.RefreshToken).count() == 0


def test_demo_login_seed_rerun_repairs_mapped_accounts_without_duplicates(db_session):
    from backend.seed_demo_data import main as seed_demo

    seed_demo()
    original_counts = {
        model: db_session.query(model).count()
        for model in (
            models.User,
            models.AuthenticationIdentity,
            models.ProviderProfile,
            models.CustomerProfile,
            models.Booking,
            models.Review,
            models.ProviderAvailability,
        )
    }
    ids = {}
    for role, email in DEMO_ACCOUNTS:
        user = db_session.query(models.User).filter_by(email=email).one()
        ids[role] = user.id
        user.role = "invalid"
        user.is_active = False
        user.is_banned = True
        user.email_verified_at = None
        identity = get_password_identity(user, db_session)
        identity.verified_at = None
        identity.password_hash = None
        if role == "provider":
            user.identity_verification_status = "rejected"
            user.qualification_verification_status = "rejected"
            profile = db_session.query(models.ProviderProfile).filter_by(user_id=user.id).one()
            profile.verification_status = "rejected"
            profile.identity_verification_status = "rejected"
            profile.qualification_verification_status = "rejected"
    db_session.commit()
    seed_demo()
    db_session.expire_all()
    for role, email in DEMO_ACCOUNTS:
        user = db_session.query(models.User).filter_by(email=email).one()
        assert user.id == ids[role]
        assert user.role == role
        assert user.is_active is True
        assert user.is_banned is False
        assert user.email_verified_at is not None
        identity = get_password_identity(user, db_session)
        assert identity.verified_at is not None
        assert identity.password_hash
        if role == "provider":
            assert user.identity_verification_status == "approved"
            assert user.qualification_verification_status == "approved"
            profile = db_session.query(models.ProviderProfile).filter_by(user_id=user.id).one()
            assert profile.verification_status == "approved"
            assert profile.identity_verification_status == "approved"
            assert profile.qualification_verification_status == "approved"
    assert {model: db_session.query(model).count() for model in original_counts} == original_counts


def test_demo_login_seed_completes_existing_provider_without_profile(db_session, demo_users):
    from backend.seed_demo_data import main as seed_demo

    provider_id = demo_users["provider"].id
    seed_demo()
    db_session.expire_all()
    profile = db_session.query(models.ProviderProfile).filter_by(user_id=provider_id).one_or_none()
    assert profile is not None
    assert profile.verification_status == "approved"
    user = db_session.query(models.User).filter_by(email="demo_provider_1@workshop.ai").one()
    assert user.id == provider_id
    assert db_session.query(models.ProviderProfile).count() == 30
