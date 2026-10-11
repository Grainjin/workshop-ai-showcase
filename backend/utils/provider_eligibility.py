"""Shared provider eligibility rules for customer-facing order actions."""

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from backend import models


INCOMPLETE_PROVIDER_ONBOARDING_CODE = "PROVIDER_ONBOARDING_INCOMPLETE"
INCOMPLETE_PROVIDER_ONBOARDING_MESSAGE = (
    "Complete all provider verification and payout details before accepting orders"
)


@dataclass(frozen=True)
class ProviderOrderEligibility:
    identity_status: str
    qualification_status: str
    payout_status: str

    @property
    def can_accept_orders(self) -> bool:
        return (
            self.identity_status == "approved"
            and self.qualification_status == "approved"
            and self.payout_status == "active"
        )


def get_provider_order_eligibility(
    provider_profile: models.ProviderProfile,
    db: Session,
) -> ProviderOrderEligibility:
    """Return the one composite decision used by actionable order flows.

    The individual statuses remain available for onboarding and admin review,
    but no order-facing caller should apply a subset of these checks.
    """

    provider = db.get(models.User, provider_profile.user_id)
    submerchant = (
        db.query(models.ProviderSubmerchant)
        .filter(models.ProviderSubmerchant.provider_profile_id == provider_profile.id)
        .first()
    )
    identity_status = (
        getattr(provider, "identity_verification_status", None)
        if provider is not None
        else None
    ) or getattr(provider_profile, "identity_verification_status", None) or "not_submitted"
    qualification_status = (
        getattr(provider, "qualification_verification_status", None)
        if provider is not None
        else None
    ) or getattr(provider_profile, "qualification_verification_status", None) or "not_submitted"
    payout_status = getattr(submerchant, "status", None) or "draft"
    return ProviderOrderEligibility(
        identity_status=identity_status,
        qualification_status=qualification_status,
        payout_status=payout_status,
    )


def require_provider_can_accept_orders(
    provider_profile: models.ProviderProfile,
    db: Session,
) -> ProviderOrderEligibility:
    eligibility = get_provider_order_eligibility(provider_profile, db)
    if not eligibility.can_accept_orders:
        raise HTTPException(
            status_code=409,
            detail={
                "code": INCOMPLETE_PROVIDER_ONBOARDING_CODE,
                "message": INCOMPLETE_PROVIDER_ONBOARDING_MESSAGE,
            },
        )
    return eligibility


def filter_provider_order_eligible_query(query: Query) -> Query:
    """Restrict a provider query to providers able to accept a new order."""

    return (
        query.join(
            models.User,
            models.User.id == models.ProviderProfile.user_id,
        )
        .join(
            models.ProviderSubmerchant,
            models.ProviderSubmerchant.provider_profile_id
            == models.ProviderProfile.id,
        )
        .filter(
            func.coalesce(
                models.User.identity_verification_status,
                models.ProviderProfile.identity_verification_status,
            )
            == "approved",
            func.coalesce(
                models.User.qualification_verification_status,
                models.ProviderProfile.qualification_verification_status,
            )
            == "approved",
            models.ProviderSubmerchant.status == "active",
        )
    )
