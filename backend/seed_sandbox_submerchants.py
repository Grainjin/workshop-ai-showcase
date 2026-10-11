"""Synchronize one demo provider's payout details with Sandbox."""

import asyncio
import argparse

from backend import models
from backend.database import SessionLocal
from backend.schemas import ProviderSubmerchantUpsert
from backend.services.marketplace import upsert_provider_submerchant
from backend.utils.marketplace_seed import (
    build_demo_submerchant_data,
    ensure_demo_submerchant_drafts,
    NEGATIVE_DEMO_PROVIDER_INDEXES,
    demo_provider_index,
)


async def run(provider_id: int) -> None:
    db = SessionLocal()
    try:
        ensure_demo_submerchant_drafts(db)
        db.commit()
        provider = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.id == provider_id)
            .first()
        )
        if not provider:
            raise ValueError(f"Provider profile {provider_id} was not found")
        user = db.get(models.User, provider.user_id)
        if not user:
            raise ValueError(f"Provider user for profile {provider_id} was not found")
        demo_index = demo_provider_index(user.email)
        if demo_index in NEGATIVE_DEMO_PROVIDER_INDEXES:
            raise ValueError(f"Provider {provider_id} is reserved as a negative sample")
        values = build_demo_submerchant_data(provider, user)
        result = await upsert_provider_submerchant(
            provider,
            ProviderSubmerchantUpsert(**values),
            db,
        )
        print(
            f"Sandbox submerchant synchronization complete: provider={provider_id} "
            f"status={result['status']} "
            f"error={result.get('iyzico_error_code')}: "
            f"{result.get('iyzico_error_message')}"
        )
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider-id",
        type=int,
        required=True,
        help="ProviderProfile.id to synchronize; only one provider is processed",
    )
    args = parser.parse_args()
    asyncio.run(run(args.provider_id))


if __name__ == "__main__":
    main()
