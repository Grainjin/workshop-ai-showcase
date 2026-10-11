"""Provider payout details with local validation."""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_db, require_provider
from backend.schemas import ProviderSubmerchantUpsert
from backend.services.marketplace import upsert_provider_submerchant
from backend.utils.marketplace import (
    format_submerchant_response,
    get_provider_submerchant,
)
from backend.utils.provider import get_or_create_provider_profile_for_onboarding
from backend.utils.response import success_response
from backend.utils.router import ApiRouter
from backend.utils.demo_mode import reject_demo_restricted_action


router = ApiRouter(tags=["Marketplace"])


@router.get("/provider/submerchant")
def get_provider_submerchant_profile(
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    provider_profile = get_or_create_provider_profile_for_onboarding(current_user, db)
    submerchant = get_provider_submerchant(provider_profile.id, db)
    db.commit()
    return success_response({"submerchant": format_submerchant_response(submerchant)})


@router.post("/provider/submerchant")
async def create_provider_submerchant_profile(
    data: ProviderSubmerchantUpsert,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "create_provider_submerchant_profile")
    provider_profile = get_or_create_provider_profile_for_onboarding(current_user, db)
    try:
        submerchant = await upsert_provider_submerchant(provider_profile, data, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response({"submerchant": submerchant})


@router.put("/provider/submerchant")
async def update_provider_submerchant_profile(
    data: ProviderSubmerchantUpsert,
    current_user: models.User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    reject_demo_restricted_action(current_user, "update_provider_submerchant_profile")
    provider_profile = get_or_create_provider_profile_for_onboarding(current_user, db)
    try:
        submerchant = await upsert_provider_submerchant(provider_profile, data, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return success_response({"submerchant": submerchant})
