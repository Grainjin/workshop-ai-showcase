import random

from sqlalchemy.orm import Session

from backend import config, models
from backend.constants import DEMO_USER_EMAILS
from backend.schemas import SubmerchantType


NEGATIVE_DEMO_PROVIDER_INDEXES = {6, 7, 8, 9}
DEMO_PROVIDER_INDEXES = tuple(
    index for index in range(1, 31) if index not in NEGATIVE_DEMO_PROVIDER_INDEXES
)

_sandbox_types = (
    [SubmerchantType.personal] * 9
    + [SubmerchantType.private_company] * 9
    + [SubmerchantType.limited_or_joint_stock_company] * 8
)
random.Random(20260928).shuffle(_sandbox_types)
DEMO_SUBMERCHANT_TYPES = dict(zip(DEMO_PROVIDER_INDEXES, _sandbox_types))

SANDBOX_SUBMERCHANT_FIXTURES = {
    SubmerchantType.personal: {
        "name": "John's market",
        "email": "email@submerchantemail.com",
        "gsm_number": "+905350000000",
        "address": "Nidakule Göztepe, Merdivenköy Mah. Bora Sok. No:1",
        "iban": "TR180006200119000006672315",
        "contact_name": "John",
        "contact_surname": "Doe",
        "identity_number": "31300864726",
        "currency": "TRY",
    },
    SubmerchantType.private_company: {
        "name": "John's market",
        "email": "email@submerchantemail.com",
        "gsm_number": "+905350000000",
        "address": "Nidakule Göztepe, Merdivenköy Mah. Bora Sok. No:1",
        "iban": "TR180006200119000006672315",
        "tax_office": "Tax office",
        "legal_company_title": "John Doe inc",
        "identity_number": "31300864726",
        "currency": "TRY",
    },
    SubmerchantType.limited_or_joint_stock_company: {
        "name": "John's market",
        "email": "email@submerchantemail.com",
        "gsm_number": "+905350000000",
        "address": "Nidakule Göztepe, Merdivenköy Mah. Bora Sok. No:1",
        "iban": "TR180006200119000006672315",
        "tax_office": "Tax office",
        "tax_number": "9261877",
        "legal_company_title": "XYZ inc",
        "currency": "TRY",
    },
}


def demo_provider_index(email: str) -> int | None:
    prefix = "demo_provider_"
    suffix = "@workshop.ai"
    if not email.startswith(prefix) or not email.endswith(suffix):
        return None
    try:
        return int(email[len(prefix) : -len(suffix)])
    except ValueError:
        return None


def build_demo_submerchant_data(
    provider: models.ProviderProfile,
    user: models.User,
):
    index = demo_provider_index(user.email) or provider.id
    submerchant_type = DEMO_SUBMERCHANT_TYPES.get(
        index, SubmerchantType.personal
    )
    return {
        "submerchant_type": submerchant_type,
        **SANDBOX_SUBMERCHANT_FIXTURES[submerchant_type],
    }


def ensure_demo_submerchant_drafts(db: Session) -> int:
    providers = (
        db.query(models.ProviderProfile, models.User)
        .join(models.User, models.User.id == models.ProviderProfile.user_id)
        .filter(models.User.email.like("demo_provider_%@workshop.ai"))
        .order_by(models.ProviderProfile.id.asc())
        .all()
    )
    created = 0
    for provider, user in providers:
        index = demo_provider_index(user.email)
        if index in NEGATIVE_DEMO_PROVIDER_INDEXES:
            continue
        existing = (
            db.query(models.ProviderSubmerchant)
            .filter(models.ProviderSubmerchant.provider_profile_id == provider.id)
            .first()
        )
        if config.DEMO_MODE and user.email == DEMO_USER_EMAILS["provider"]:
            if existing is None:
                existing = models.ProviderSubmerchant(provider_profile_id=provider.id)
                db.add(existing)
                created += 1
            # Local navigation readiness only. Never create a vendor key or payout identity.
            existing.submerchant_type = SubmerchantType.personal.value
            existing.submerchant_external_id = f"demo-provider-{provider.id}"
            existing.name = "Simulated demo payout account"
            existing.email = user.email
            existing.gsm_number = ""
            existing.address = "Public demo — no real payouts"
            existing.currency = "TRY"
            existing.status = "active"
            for field in ("submerchant_key", "iban", "contact_name", "contact_surname",
                          "identity_number", "tax_office", "tax_number", "legal_company_title",
                          "iyzico_error_code", "iyzico_error_message", "last_synced_at"):
                setattr(existing, field, None)
            continue
        if existing:
            continue
        values = build_demo_submerchant_data(provider, user)
        db.add(
            models.ProviderSubmerchant(
                provider_profile_id=provider.id,
                submerchant_type=values["submerchant_type"].value,
                submerchant_external_id=f"provider-{provider.id}",
                name=values["name"],
                email=values["email"],
                gsm_number=values["gsm_number"],
                address=values["address"],
                iban=values["iban"],
                contact_name=values.get("contact_name"),
                contact_surname=values.get("contact_surname"),
                identity_number=values.get("identity_number"),
                tax_office=values.get("tax_office"),
                tax_number=values.get("tax_number"),
                legal_company_title=values.get("legal_company_title"),
                currency=values["currency"],
                status="draft",
            )
        )
        created += 1
    return created
