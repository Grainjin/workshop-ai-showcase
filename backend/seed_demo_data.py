import random
from datetime import date, timedelta
from decimal import Decimal

from backend import config, models
from backend.auth import create_password_identity, hash_password
from backend.utils.verification import get_user_phone_number
from backend.constants import ALLOWED_PROVIDER_TAGS, DEMO_PASSWORD, DEMO_USER_EMAILS
from backend.core.clock import utc_now
from backend.database import SessionLocal
from backend.utils.service_locations import seed_service_locations
from backend.utils.marketplace_seed import ensure_demo_submerchant_drafts

TAGS = ALLOWED_PROVIDER_TAGS
DEFAULT_PROVINCE = "Istanbul"
ADMIN_EMAIL = DEMO_USER_EMAILS["admin"]

ISTANBUL_LOCATIONS = [
    (41.0082, 28.9784),
    (41.0430, 29.0094),
    (40.9903, 29.0294),
    (41.0255, 28.9744),
    (41.0632, 28.9270),
    (40.9833, 28.8738),
    (41.0766, 29.0522),
    (41.0343, 28.8564),
    (40.9193, 29.1557),
    (41.1827, 28.7407),
]

POSITIVE_COMMENTS = [
    "Arrived on time and left everything clean.",
    "Clear communication and fair pricing.",
    "Great attitude and attention to detail.",
    "Skilled and fixed the issue quickly.",
    "Smooth booking and good overall experience.",
    "Explained everything clearly with no surprise charges.",
    "Well-equipped and very efficient.",
    "Patient and thorough with details.",
    "Finished faster than expected; would recommend.",
    "Professional and followed up afterward.",
]

NEUTRAL_COMMENTS = [
    "Service was OK; speed was average.",
    "Fair price; communication was fine.",
    "Issue fixed but wait time was long.",
    "Acceptable overall; nothing exceptional.",
    "Attitude was fine; details could be better.",
]

NEGATIVE_COMMENTS = [
    "Arrived late with slow communication.",
    "Higher price than expected; explanation unclear.",
    "Average attitude; not a great experience.",
    "Slow work; needed follow-up.",
    "Did not clean up well afterward.",
    "Quote changed unexpectedly.",
    "Slow replies and disorganized scheduling.",
]

BUSINESS_WORDS = {
    "cleaning": ["CleanCare", "Home Shine", "Fresh Home", "Neat Service"],
    "childcare": ["Child Care", "Family Care", "Kids Helper", "Safe Nanny"],
    "elderly_care": ["Elder Care", "Senior Support", "Care Companion", "Home Assist"],
    "electrician": ["Bright Electric", "Safe Wiring", "Power Fix", "Home Electric"],
    "plumbing": ["Pipe Fix", "Water Works", "Rapid Plumbing", "Home Plumbing"],
    "painter": ["Fresh Paint", "Color Works", "Wall Renew", "Paint Studio"],
    "locksmith": ["Lock Master", "Key Care", "Door Lock Fix", "Rapid Locksmith"],
    "technician": ["Tech Repair", "Device Fix", "Rapid Repair", "Home Tech"],
    "moving": ["Move Helper", "Quick Move", "City Movers", "Home Moving"],
    "other": ["Local Helper", "City Service", "Home Support", "Everyday Help"],
}

BIOS = {
    "cleaning": "Home cleaning, deep cleaning, and post-move cleaning.",
    "childcare": "Childcare, pickup companionship, and daily parenting help.",
    "elderly_care": "Elder companionship, daily care, and basic living assistance.",
    "electrician": "On-site electrical work: circuits, outlets, lighting, switches.",
    "plumbing": "Plumbing: leaks, toilets, faucets, drains.",
    "painter": "Interior painting, touch-ups, and small refreshes.",
    "locksmith": "Locksmith: unlock, rekey, lock repair, keys.",
    "technician": "Home appliance repair, installation, and emergency visits.",
    "moving": "Moving, hauling, furniture moves, and local transport.",
    "other": "Other flexible local on-site services and daily help.",
}


def pick_provider_tags(index: int):
    primary_tag = TAGS[index % len(TAGS)]
    tags = [primary_tag]

    if index % 3 == 0 and primary_tag not in ["technician", "other"]:
        tags.append("technician")

    if index % 7 == 0:
        extra_tag = TAGS[(index + 2) % len(TAGS)]
        if extra_tag not in tags:
            tags.append(extra_tag)

    return tags


def pick_reviews(rng=None):
    rng = rng if rng is not None else random.Random(config.WORKSHOP_DEMO_SEED)
    positive_count = rng.randint(6, 8)
    negative_count = rng.randint(1, 2)
    neutral_count = 10 - positive_count - negative_count
    reviews = []

    for _ in range(positive_count):
        reviews.append((rng.choice([4, 5]), rng.choice(POSITIVE_COMMENTS)))
    for _ in range(neutral_count):
        reviews.append((3, rng.choice(NEUTRAL_COMMENTS)))
    for _ in range(negative_count):
        reviews.append((rng.choice([1, 2]), rng.choice(NEGATIVE_COMMENTS)))

    rng.shuffle(reviews)
    return reviews


def ensure_password_identity(user: models.User, db):
    existing = (
        db.query(models.AuthenticationIdentity)
        .filter(
            models.AuthenticationIdentity.user_id == user.id,
            models.AuthenticationIdentity.identity_provider == "email_password",
        )
        .first()
    )
    if existing:
        now = utc_now()
        existing.provider_subject = user.email
        if not existing.password_hash:
            existing.password_hash = hash_password(DEMO_PASSWORD)
        if existing.verified_at is None:
            existing.verified_at = now
        if user.email_verified_at is None:
            user.email_verified_at = existing.verified_at
        return existing
    return create_password_identity(user, DEMO_PASSWORD, db, verified=True)


def ensure_seed_verified(user: models.User, db, role: str):
    user.role = role
    user.is_active = True
    user.is_banned = False
    if role == "provider":
        user.identity_verification_status = "approved"
        user.qualification_verification_status = "approved"
    ensure_password_identity(user, db)
    if user.phone_verified_at is None and get_user_phone_number(user, db):
        user.phone_verified_at = utc_now()
    return user


def create_demo_admin(db):
    user = db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first()
    if not user:
        user = models.User(
            name="Demo Admin",
            email=ADMIN_EMAIL,
            role="admin",
            is_active=True,
            is_banned=False,
            last_login_at=None,
            created_at=utc_now(),
        )
        db.add(user)
        db.flush()
    ensure_seed_verified(user, db, "admin")
    return user


def create_demo_customers(db, location_seeds=None, *, rng=None):
    rng = rng if rng is not None else random.Random(config.WORKSHOP_DEMO_SEED)
    location_seeds = location_seeds or seed_service_locations(db)
    istanbul_districts = [
        location.id
        for code, location in location_seeds.items()
        if code.startswith("tr-istanbul-city-")
    ]
    customers = []

    for index in range(5):
        email = (
            DEMO_USER_EMAILS["customer"]
            if index == 0
            else f"demo_customer_{index + 1}@workshop.ai"
        )
        user = db.query(models.User).filter(models.User.email == email).first()

        if not user:
            user = models.User(
                name=f"Istanbul Customer {index + 1}",
                email=email,
                role="customer",
                is_active=True,
                is_banned=False,
                last_login_at=None,
                created_at=utc_now(),
            )
            db.add(user)
            db.flush()

        profile = (
            db.query(models.CustomerProfile)
            .filter(models.CustomerProfile.user_id == user.id)
            .first()
        )

        if not profile:
            latitude, longitude = rng.choice(ISTANBUL_LOCATIONS)
            profile = models.CustomerProfile(
                user_id=user.id,
                phone_number=f"+9055500000{index + 1:02d}",
                address=f"{index + 1} Istanbul Demo Street",
                service_province=DEFAULT_PROVINCE,
                service_location_id=istanbul_districts[index % len(istanbul_districts)],
                latitude=latitude,
                longitude=longitude,
                current_address="Istanbul current location",
                current_latitude=latitude,
                current_longitude=longitude,
                default_service_address=f"{index + 1} Istanbul Demo Street",
                default_service_latitude=latitude,
                default_service_longitude=longitude,
                notes="Demo customer for AI recommendation testing",
            )
            db.add(profile)

        ensure_seed_verified(user, db, "customer")
        customers.append(user)

    return customers


def get_seed_admin_id(db):
    admin = db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first()
    return admin.id if admin else None


def create_demo_providers(db, customers, location_seeds=None, *, rng=None):
    rng = rng if rng is not None else random.Random(config.WORKSHOP_DEMO_SEED)
    location_seeds = location_seeds or seed_service_locations(db)
    istanbul_districts = [
        location.id
        for code, location in location_seeds.items()
        if code.startswith("tr-istanbul-city-")
    ]
    created_provider_count = 0
    created_availability_count = 0
    created_booking_count = 0
    created_review_count = 0
    now = utc_now()

    for index in range(30):
        email = (
            DEMO_USER_EMAILS["provider"]
            if index == 0
            else f"demo_provider_{index + 1}@workshop.ai"
        )
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if existing_user:
            ensure_seed_verified(existing_user, db, "provider")
            existing_profile = (
                db.query(models.ProviderProfile)
                .filter(models.ProviderProfile.user_id == existing_user.id)
                .first()
            )
            if existing_profile:
                existing_profile.verification_status = "approved"
                existing_profile.identity_verification_status = "approved"
                existing_profile.qualification_verification_status = "approved"
                continue

        tags = pick_provider_tags(index)
        primary_tag = tags[0]
        latitude, longitude = rng.choice(ISTANBUL_LOCATIONS)
        business_name = f"Istanbul {rng.choice(BUSINESS_WORDS[primary_tag])}"

        provider_user = existing_user
        if provider_user is None:
            provider_user = models.User(
                name=f"Istanbul Provider {index + 1}",
                email=email,
                role="provider",
                is_active=True,
                is_banned=False,
                last_login_at=None,
                identity_verification_status="approved",
                qualification_verification_status="approved",
                created_at=now,
            )
            db.add(provider_user)
            db.flush()
        provider_user.first_name = provider_user.first_name or "Istanbul"
        provider_user.last_name = provider_user.last_name or f"Provider {index + 1}"
        provider_profile = models.ProviderProfile(
            user_id=provider_user.id,
            business_name=business_name,
            bio=BIOS[primary_tag],
            phone_number=f"+9055510000{index + 1:02d}",
            address=f"{index + 1} Istanbul Provider Street",
            service_province=DEFAULT_PROVINCE,
            service_location_id=istanbul_districts[index % len(istanbul_districts)],
            latitude=latitude,
            longitude=longitude,
            tags=",".join(tags),
            certificate_name=f"{primary_tag} service credential",
            certificate_url=f"https://example.com/certificates/provider-{index + 1}.jpg",
            hourly_rate=rng.randint(45, 160),
            verification_status="approved",
            identity_verification_status="approved",
            qualification_verification_status="approved",
            verification_note="Demo provider approved for AI testing",
        )
        db.add(provider_profile)
        db.flush()
        identity_application = models.IdentityVerificationApplication(
            user_id=provider_user.id,
            submitted_first_name=provider_user.first_name,
            submitted_last_name=provider_user.last_name,
            date_of_birth=date(1990, 1, 1),
            document_type="national_id",
            status="approved",
            review_note=None,
            reviewed_by_user_id=get_seed_admin_id(db),
            submitted_at=now,
            reviewed_at=now,
        )
        db.add(identity_application)
        db.flush()
        db.add(
            models.IdentityVerificationFile(
                application_id=identity_application.id,
                file_url=(
                    f"https://example.com/demo-verification/"
                    f"provider-{index + 1}-identity.pdf"
                ),
                original_file_name=f"provider-{index + 1}-identity.pdf",
                content_type="application/pdf",
                sort_order=0,
            )
        )
        ensure_seed_verified(provider_user, db, "provider")
        created_provider_count += 1

        for weekday in range(1, 8):
            availability = models.ProviderAvailability(
                provider_profile_id=provider_profile.id,
                weekday=weekday,
                start_time="08:00",
                end_time="20:00",
                is_available=True,
            )
            db.add(availability)
            created_availability_count += 1

        for review_index, (rating, comment) in enumerate(pick_reviews(rng)):
            customer = rng.choice(customers)
            start_time = now - timedelta(days=rng.randint(1, 180))
            end_time = start_time + timedelta(hours=rng.randint(1, 5))
            amount = Decimal(str(round(provider_profile.hourly_rate * rng.uniform(1.0, 4.0), 2)))

            booking = models.Booking(
                customer_id=customer.id,
                provider_profile_id=provider_profile.id,
                chat_room_id=None,
                service_category=primary_tag,
                service_description=f"{primary_tag} demo service {review_index + 1}",
                service_address="Istanbul demo service address",
                service_latitude=latitude,
                service_longitude=longitude,
                customer_current_address="Istanbul current location",
                customer_current_latitude=latitude,
                customer_current_longitude=longitude,
                booking_at=start_time - timedelta(days=1),
                scheduled_start_time=start_time,
                scheduled_end_time=end_time,
                completed_at=end_time,
                total_amount=amount,
                quote_amount=amount,
                quote_message="Demo quote for AI testing",
                quoted_at=start_time - timedelta(hours=20),
                status="completed",
                status_note="Demo completed booking",
            )
            db.add(booking)
            db.flush()
            created_booking_count += 1
            db.add(models.BookingQuoteRevision(
                booking_id=booking.id,
                revision_number=1,
                quote_amount=amount,
                quote_message="Demo quote for AI testing",
                created_by_user_id=provider_user.id,
                created_at=booking.quoted_at,
                customer_confirmed_at=start_time - timedelta(hours=19),
            ))

            review = models.Review(
                booking_id=booking.id,
                customer_id=customer.id,
                provider_profile_id=provider_profile.id,
                rating=rating,
                comment=comment,
                created_at=end_time,
                is_visible=1,
                embedding_status="pending",
                embedding_error=None,
                embedding_synced_at=None,
            )
            db.add(review)
            created_review_count += 1

    return {
        "providers": created_provider_count,
        "availabilities": created_availability_count,
        "bookings": created_booking_count,
        "reviews": created_review_count,
    }


def assign_existing_demo_locations(db, location_seeds):
    istanbul_districts = [
        location.id
        for code, location in location_seeds.items()
        if code.startswith("tr-istanbul-city-")
    ]
    if not istanbul_districts:
        return

    customer_profiles = (
        db.query(models.CustomerProfile)
        .filter(
            models.CustomerProfile.service_province == DEFAULT_PROVINCE,
            models.CustomerProfile.service_location_id.is_(None),
        )
        .order_by(models.CustomerProfile.id.asc())
        .all()
    )
    provider_profiles = (
        db.query(models.ProviderProfile)
        .filter(
            models.ProviderProfile.service_province == DEFAULT_PROVINCE,
            models.ProviderProfile.service_location_id.is_(None),
        )
        .order_by(models.ProviderProfile.id.asc())
        .all()
    )
    for index, profile in enumerate(customer_profiles):
        profile.service_location_id = istanbul_districts[index % len(istanbul_districts)]
    for index, profile in enumerate(provider_profiles):
        profile.service_location_id = istanbul_districts[index % len(istanbul_districts)]


def ensure_mapped_demo_provider_services(db):
    """Repair local demo operating records without changing real onboarding."""
    if not config.DEMO_MODE:
        return
    profile = db.query(models.ProviderProfile).join(models.User).filter(
        models.User.email == DEMO_USER_EMAILS["provider"],
    ).one()
    for category in profile.tags.split(","):
        if category not in ALLOWED_PROVIDER_TAGS:
            continue
        service = db.query(models.ProviderApprovedService).filter_by(
            provider_profile_id=profile.id, service_category=category,
        ).first()
        if service is None:
            service = models.ProviderApprovedService(
                provider_profile_id=profile.id, service_category=category,
            )
            db.add(service)
        service.is_enabled = True
    if profile.service_location_id is not None:
        area = db.query(models.ProviderServiceArea).filter_by(
            provider_profile_id=profile.id, service_location_id=profile.service_location_id,
        ).first()
        if area is None:
            db.add(models.ProviderServiceArea(
                provider_profile_id=profile.id, service_location_id=profile.service_location_id,
            ))


def seed_demo_data(db):
    """Seed demo fixtures without committing; the caller owns the transaction."""
    rng = random.Random(config.WORKSHOP_DEMO_SEED)
    location_seeds = seed_service_locations(db)
    create_demo_admin(db)
    customers = create_demo_customers(db, location_seeds, rng=rng)
    result = create_demo_providers(db, customers, location_seeds, rng=rng)
    assign_existing_demo_locations(db, location_seeds)
    ensure_mapped_demo_provider_services(db)
    result["submerchant_drafts"] = ensure_demo_submerchant_drafts(db)
    return result


def main():
    db = SessionLocal()

    try:
        result = seed_demo_data(db)
        db.commit()
        print("Demo data inserted successfully.")
        print(result)
        print(f"Demo password for all seeded accounts: {DEMO_PASSWORD}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
