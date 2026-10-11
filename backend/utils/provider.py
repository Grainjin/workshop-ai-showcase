from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.utils.formatters import format_provider_profile_response
from backend.utils.review import get_provider_rating_summary
from backend.core.clock import utc_now


def format_provider_profile_with_rating(profile, db: Session):
    result = format_provider_profile_response(
        profile, include_verification_documents=False
    )
    result.update(get_provider_rating_summary(profile.id, db))

    return result


def format_favorite_provider_response(favorite, db: Session):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.id == favorite.provider_profile_id)
        .first()
    )

    return {
        "id": favorite.id,
        "customer_id": favorite.customer_id,
        "provider_profile_id": favorite.provider_profile_id,
        "created_at": favorite.created_at,
        "provider": (
            format_provider_profile_with_rating(provider_profile, db)
            if provider_profile
            else None
        ),
    }


def get_provider_profile_for_user(user_id: int, db: Session):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.user_id == user_id)
        .first()
    )

    if not provider_profile:
        raise HTTPException(
            status_code=404,
            detail="Provider profile not found",
        )

    return provider_profile


def get_or_create_provider_profile_for_onboarding(user: models.User, db: Session):
    """Return a draft profile so payout onboarding can start independently."""

    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(models.ProviderProfile.user_id == user.id)
        .first()
    )
    if provider_profile:
        return provider_profile

    provider_profile = models.ProviderProfile(
        user_id=user.id,
        business_name=(user.name or "Provider").strip(),
        bio="",
        phone_number="",
        address="",
        service_province="",
        tags="",
        certificate_name="",
        certificate_url="",
        hourly_rate=0,
        verification_status="pending",
        entity_type="personal",
        identity_verification_status=user.identity_verification_status or "not_submitted",
        qualification_verification_status=(
            user.qualification_verification_status or "not_submitted"
        ),
    )
    db.add(provider_profile)
    db.flush()
    return provider_profile


def add_provider_verification_history(
    profile: models.ProviderProfile,
    old_status: str,
    new_status: str,
    note: str | None,
    current_user: models.User,
    db: Session,
    verification_step: str = "qualification",
):
    history = models.ProviderVerificationHistory(
        provider_profile_id=profile.id,
        changed_by_user_id=current_user.id,
        old_status=old_status,
        new_status=new_status,
        note=note,
        changed_at=utc_now(),
        verification_step=verification_step,
    )

    db.add(history)


def require_provider_qualification_approved(profile: models.ProviderProfile):
    """Raise unless the provider has passed the customer-facing qualification gate."""
    status = getattr(profile, "qualification_verification_status", None)
    if status is None:
        status = profile.verification_status
    if status != "approved":
        raise HTTPException(
            status_code=403,
            detail="Provider qualification approval is required for this action",
        )


def require_provider_identity_approved(profile: models.ProviderProfile):
    status = getattr(profile, "identity_verification_status", profile.verification_status)
    if status != "approved":
        raise HTTPException(
            status_code=403,
            detail="Provider identity approval is required for this action",
        )
