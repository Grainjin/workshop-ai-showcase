"""Third-party login token verification.

After Google/Apple auth the frontend receives an id_token.
The backend verifies signature, expiry, issuer, client id and, when the app
sent one, the nonce that ties the token to this sign-in attempt.
"""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from hmac import compare_digest
from urllib.request import urlopen
import json

from fastapi import HTTPException
from jose import JWTError, jwt

from backend.config import (
    APPLE_CLIENT_IDS,
    APPLE_TOKEN_ISSUER,
    GOOGLE_CLIENT_IDS,
)

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
GOOGLE_TOKEN_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass
class VerifiedSocialIdentity:
    provider: str
    provider_user_id: str
    # Only set when the provider has verified the address.
    email: str | None
    name: str | None
    given_name: str | None = None
    family_name: str | None = None


def verify_social_identity(
    provider: str,
    id_token: str,
    nonce: str | None = None,
) -> VerifiedSocialIdentity:
    if provider == "google":
        return verify_google_identity(id_token, nonce)

    if provider == "apple":
        return verify_apple_identity(id_token, nonce)

    raise HTTPException(status_code=400, detail="Unsupported social login provider")


def verify_google_identity(id_token: str, nonce: str | None = None) -> VerifiedSocialIdentity:
    if not GOOGLE_CLIENT_IDS:
        raise HTTPException(
            status_code=500,
            detail="WORKSHOP_GOOGLE_CLIENT_IDS is not configured",
        )

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        payload = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            audience=None,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Google ID token") from exc

    if payload.get("iss") not in GOOGLE_TOKEN_ISSUERS:
        raise HTTPException(status_code=401, detail="Invalid Google token issuer")

    if payload.get("aud") not in GOOGLE_CLIENT_IDS:
        raise HTTPException(status_code=401, detail="Invalid Google token audience")

    if payload.get("email") and payload.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google email is not verified")

    # Google echoes the nonce unchanged.
    if nonce is not None and not _same(payload.get("nonce"), nonce):
        raise HTTPException(status_code=401, detail="Google token nonce does not match")

    provider_user_id = payload.get("sub")
    if not provider_user_id:
        raise HTTPException(status_code=401, detail="Google token has no subject")

    return VerifiedSocialIdentity(
        provider="google",
        provider_user_id=provider_user_id,
        email=payload.get("email"),
        name=payload.get("name"),
        given_name=payload.get("given_name"),
        family_name=payload.get("family_name"),
    )


def verify_apple_identity(id_token: str, nonce: str | None = None) -> VerifiedSocialIdentity:
    if not APPLE_CLIENT_IDS:
        raise HTTPException(
            status_code=500,
            detail="WORKSHOP_APPLE_CLIENT_IDS is not configured",
        )

    try:
        header = jwt.get_unverified_header(id_token)
        signing_key = find_apple_signing_key(header.get("kid"))
        payload = jwt.decode(
            id_token,
            signing_key,
            algorithms=["RS256"],
            issuer=APPLE_TOKEN_ISSUER,
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid Apple identity token"
        ) from exc

    if payload.get("aud") not in APPLE_CLIENT_IDS:
        raise HTTPException(status_code=401, detail="Invalid Apple token audience")

    # The app hands Apple the SHA-256 of its raw nonce, so the token carries
    # the hash. A nonce is required: without it a leaked token could be replayed.
    if nonce is None:
        raise HTTPException(status_code=400, detail="Apple sign-in needs a nonce")
    if not _same(payload.get("nonce"), sha256(nonce.encode("utf-8")).hexdigest()):
        raise HTTPException(status_code=401, detail="Apple token nonce does not match")

    provider_user_id = payload.get("sub")
    if not provider_user_id:
        raise HTTPException(status_code=401, detail="Apple token has no subject")

    # Apple sends email_verified as "true" or true. Relay addresses
    # (privaterelay.appleid.com) are verified too.
    email_verified = str(payload.get("email_verified", "")).lower() == "true"

    return VerifiedSocialIdentity(
        provider="apple",
        provider_user_id=provider_user_id,
        email=payload.get("email") if email_verified else None,
        name=None,
    )


def _same(actual, expected: str) -> bool:
    return isinstance(actual, str) and compare_digest(actual, expected)


def find_apple_signing_key(key_id: str | None):
    if not key_id:
        raise HTTPException(status_code=401, detail="Apple token has no key id")

    jwks = get_apple_jwks()

    for key in jwks.get("keys", []):
        if key.get("kid") == key_id:
            return key

    raise HTTPException(status_code=401, detail="Apple signing key not found")


@lru_cache(maxsize=1)
def get_apple_jwks():
    with urlopen(APPLE_JWKS_URL, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))
