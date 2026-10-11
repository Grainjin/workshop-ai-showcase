"""Email and phone verification helpers. Email codes live in email_verification_service; phone is still a demo."""

from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_now


def mark_email_verified(user: models.User, identity: models.AuthenticationIdentity | None = None):
    now = get_now()
    user.email_verified_at = now
    if identity is not None:
        identity.verified_at = now
    return user


def mark_phone_verified(user: models.User):
    user.phone_verified_at = get_now()
    return user


def apply_phone_number_change(
    user: models.User,
    previous_phone: str | None,
    next_phone: str | None,
):
    if (previous_phone or "").strip() != (next_phone or "").strip():
        user.phone_verified_at = None


def get_user_phone_number(user: models.User, db: Session) -> str | None:
    if user.role == "customer":
        profile = (
            db.query(models.CustomerProfile)
            .filter(models.CustomerProfile.user_id == user.id)
            .first()
        )
    elif user.role == "provider":
        profile = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.user_id == user.id)
            .first()
        )
    else:
        return None

    if profile is None:
        return None

    phone = (profile.phone_number or "").strip()
    return phone or None
