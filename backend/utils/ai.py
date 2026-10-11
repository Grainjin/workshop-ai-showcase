import re
from datetime import datetime

from sqlalchemy.orm import Session

from backend import models
from backend.constants import AI_RECOMMENDATION_PROVIDER_TAGS
from backend.schemas import BookingStatus, PaymentStatus, ProviderVerificationStatus
from backend.utils.availability import is_provider_available_for_datetime_range
from backend.utils.formatters import tags_to_list
from backend.utils.location import (
    calculate_distance_km,
    has_location,
)
from backend.utils.service_locations import (
    filter_provider_query_by_location,
    normalize_location_name,
)


AI_RECOMMENDATION_TAG_ALIASES = {
    "cleaning": [
        "cleaning",
        "clean",
        "housekeeping",
        "deep clean",
        "maid",
        "sanitize",
        "tidy",
    ],
    "childcare": [
        "childcare",
        "child care",
        "babysit",
        "babysitting",
        "nanny",
        "kids",
        "children",
        "daycare",
    ],
    "elderly_care": [
        "elderly care",
        "elderly_care",
        "senior care",
        "elder care",
        "caregiver",
        "companion care",
        "home care",
    ],
    "electrician": [
        "electrician",
        "electrical",
        "wiring",
        "outlet",
        "circuit",
        "breaker",
        "lighting",
        "switch",
    ],
    "plumbing": [
        "plumbing",
        "plumber",
        "pipe",
        "leak",
        "toilet",
        "drain",
        "clog",
        "faucet",
        "water heater",
    ],
    "painter": [
        "painter",
        "painting",
        "paint",
        "wall",
        "repaint",
        "touch up",
    ],
    "locksmith": [
        "locksmith",
        "lock",
        "unlock",
        "rekey",
        "door lock",
        "key",
    ],
    "technician": [
        "technician",
        "repair",
        "fix",
        "install",
        "appliance",
        "hvac",
        "air conditioning",
        "maintenance",
    ],
    "moving": [
        "moving",
        "mover",
        "move",
        "relocation",
        "haul",
        "furniture move",
    ],
}


def normalize_ai_recommendation_tags(tags: list[str] | None, query: str = ""):
    normalized_tags = []
    query_text = query.lower()

    for raw_tag in tags or []:
        clean_tag = raw_tag.strip().lower()

        for standard_tag, aliases in AI_RECOMMENDATION_TAG_ALIASES.items():
            if clean_tag == standard_tag or clean_tag in aliases:
                if standard_tag not in normalized_tags:
                    normalized_tags.append(standard_tag)
                break

    for standard_tag, aliases in AI_RECOMMENDATION_TAG_ALIASES.items():
        if standard_tag in normalized_tags:
            continue

        if standard_tag in query or any(alias.lower() in query_text for alias in aliases):
            normalized_tags.append(standard_tag)

    return [
        tag for tag in normalized_tags if tag in AI_RECOMMENDATION_PROVIDER_TAGS
    ]


def parse_user_service_need(query: str):
    normalized_query = query.lower()

    matched_tags = []

    for tag, keywords in AI_RECOMMENDATION_TAG_ALIASES.items():
        for keyword in keywords:
            if keyword in normalized_query:
                matched_tags.append(tag)
                break

    budget_preference = None

    cheap_keywords = ["cheap", "affordable", "budget", "low price", "inexpensive"]
    quality_keywords = [
        "reliable",
        "good reviews",
        "high rating",
        "experienced",
        "professional",
        "quality",
    ]

    for keyword in cheap_keywords:
        if keyword in normalized_query:
            budget_preference = "cheap"
            break

    for keyword in quality_keywords:
        if keyword in normalized_query:
            budget_preference = "quality"
            break

    return {
        "matched_tags": matched_tags,
        "budget_preference": budget_preference,
    }


_CAPABILITY_ONLY_RE = re.compile(
    r"^\s*(?:hi[,!.\s]+|hello[,!.\s]+|hey[,!.\s]+)?"
    r"(?:"
    r"who are you|what are you|what can you do|what do you do|"
    r"how (?:do|can) i use you|what can you help(?: me)? with|"
    r"help|capabilities|"
    r"你是谁|你能做什么|怎么用|"
    r"kimsin|neler yapabilirsin|ne yapabilirsin"
    r")[\s!.?]*$",
    re.IGNORECASE,
)

_CASUAL_GREETING_ONLY_RE = re.compile(
    r"^\s*(?:"
    r"hi|hello|hey|yo|sup|thanks|thank you|cheers|"
    r"merhaba|selam|iyi günler|"
    r"你好|嗨|哈喽|谢谢"
    r")[\s!.?]*$",
    re.IGNORECASE,
)

CASUAL_LOCAL_ANSWER = (
    "I'm Workshop AI. I can help find nearby providers, compare reviews, "
    "and draft a booking. Tell me the service you need."
)


def looks_like_capability_question(query: str) -> bool:
    return bool(_CAPABILITY_ONLY_RE.match((query or "").strip()))


def looks_like_casual_greeting_only(query: str) -> bool:
    return bool(_CASUAL_GREETING_ONLY_RE.match((query or "").strip()))


def looks_like_review_summary_question(query: str):
    review_summary_keywords = [
        "review",
        "reviews",
        "rating",
        "reputation",
        "attitude",
        "price",
        "quote",
        "expensive",
        "cheap",
        "compare",
        "comparison",
        "which one",
        "feedback",
    ]

    for keyword in review_summary_keywords:
        if keyword in query:
            return True

    return False


def find_provider_candidates(
    matched_tags: list[str],
    service_province: str | None,
    max_price: float | None,
    latitude: float | None,
    longitude: float | None,
    max_distance_km: float | None,
    scheduled_start_time: datetime | None,
    scheduled_end_time: datetime | None,
    db: Session,
    service_location_id: int | None = None,
):
    query = db.query(models.ProviderProfile).filter(
        models.ProviderProfile.qualification_verification_status
        == ProviderVerificationStatus.approved
    )

    query = filter_provider_query_by_location(
        query,
        db,
        location_id=service_location_id,
        province_name=service_province,
    )

    if max_price is not None:
        query = query.filter(models.ProviderProfile.hourly_rate <= max_price)

    providers = query.all()

    if not matched_tags:
        matched_providers = providers
    else:
        matched_providers = []

        for provider in providers:
            provider_tags = tags_to_list(provider.tags)

            for tag in matched_tags:
                if tag in provider_tags:
                    matched_providers.append(provider)
                    break

    if scheduled_start_time is not None and scheduled_end_time is not None:
        matched_providers = [
            provider
            for provider in matched_providers
            if is_provider_available_for_datetime_range(
                provider.id,
                scheduled_start_time,
                scheduled_end_time,
                db,
            )
        ]

    if not has_location(latitude, longitude):
        return matched_providers, {}

    location_filtered_providers = []
    distance_by_provider_id = {}

    for provider in matched_providers:
        if not has_location(provider.latitude, provider.longitude):
            continue

        distance_km = calculate_distance_km(
            latitude,
            longitude,
            provider.latitude,
            provider.longitude,
        )

        if max_distance_km is not None and distance_km > max_distance_km:
            continue

        distance_by_provider_id[provider.id] = distance_km
        location_filtered_providers.append(provider)

    return location_filtered_providers, distance_by_provider_id


def get_provider_ai_stats(provider_profile_id: int, db: Session):
    completed_bookings = (
        db.query(models.Booking)
        .filter(
            models.Booking.provider_profile_id == provider_profile_id,
            models.Booking.status == BookingStatus.completed,
        )
        .count()
    )

    complaints = (
        db.query(models.Complaint)
        .filter(
            models.Complaint.booking_id.in_(
                db.query(models.Booking.id).filter(
                    models.Booking.provider_profile_id == provider_profile_id
                )
            )
        )
        .count()
    )

    refunds = (
        db.query(models.Payment)
        .filter(
            models.Payment.provider_profile_id == provider_profile_id,
            models.Payment.status == PaymentStatus.refunded,
        )
        .count()
    )

    reviews = (
        db.query(models.Review)
        .filter(
            models.Review.provider_profile_id == provider_profile_id,
            models.Review.is_visible == 1,
        )
        .all()
    )

    if reviews:
        average_rating = round(
            sum(review.rating for review in reviews) / len(reviews),
            2,
        )
    else:
        average_rating = 0

    return {
        "completed_bookings": completed_bookings,
        "complaints": complaints,
        "refunds": refunds,
        "average_rating": average_rating,
        "review_count": len(reviews),
    }


def calculate_provider_match_score(
    provider: models.ProviderProfile,
    matched_tags: list[str],
    service_province: str | None,
    max_price: float | None,
    budget_preference: str | None,
    distance_km: float | None,
    is_available_for_requested_time: bool,
    db: Session,
):
    score = 0
    reasons = []

    provider_tags = tags_to_list(provider.tags)

    matched_provider_tags = []

    for tag in matched_tags:
        if tag in provider_tags:
            matched_provider_tags.append(tag)

    if matched_tags:
        tag_score = int(len(matched_provider_tags) / len(matched_tags) * 40)
        score += tag_score

        if matched_provider_tags:
            reasons.append(f"Tag match: {', '.join(matched_provider_tags)}")
    else:
        score += 10
        reasons.append("No specific tag matched; showing general candidates")

    if (
        service_province
        and normalize_location_name(service_province)
        in normalize_location_name(provider.service_province)
    ):
        score += 15
        reasons.append("Service province matches")

    if max_price is not None and provider.hourly_rate <= max_price:
        score += 10
        reasons.append("Price within budget")

    if distance_km is not None:
        if distance_km <= 3:
            score += 15
        elif distance_km <= 10:
            score += 12
        elif distance_km <= 20:
            score += 8
        else:
            score += 5

        reasons.append(f"About {distance_km} km away, within service range")

    if is_available_for_requested_time:
        score += 10
        reasons.append("Available for requested time slot")

    stats = get_provider_ai_stats(provider.id, db)

    if stats["average_rating"] > 0:
        rating_score = int(stats["average_rating"] / 5 * 15)
        score += rating_score
        reasons.append(f"Average rating {stats['average_rating']}")

    if stats["completed_bookings"] > 0:
        completed_score = min(stats["completed_bookings"], 10)
        score += completed_score
        reasons.append(f"Completed {stats['completed_bookings']} bookings")

    penalty = min(stats["complaints"] + stats["refunds"], 10)
    score -= penalty

    if penalty > 0:
        reasons.append(
            f"{stats['complaints']} complaint(s) and {stats['refunds']} refund(s) on record"
        )

    if budget_preference == "cheap" and max_price is not None:
        if provider.hourly_rate <= max_price * 0.8:
            score += 5
            reasons.append("Lower price, matches budget preference")

    if budget_preference == "quality":
        if stats["average_rating"] >= 4.5:
            score += 5
            reasons.append("Higher rating, matches quality preference")

    score = max(0, min(score, 100))

    return {
        "match_score": score,
        "matched_tags": matched_provider_tags,
        "reason": "; ".join(reasons) if reasons else "No clear match reason",
        "reason_tags": reasons if reasons else ["No clear match reason"],
        "stats": stats,
    }


def build_provider_recommendations(
    query: str,
    matched_tags: list[str],
    service_province: str | None,
    max_price: float | None,
    budget_preference: str | None,
    db: Session,
    latitude: float | None = None,
    longitude: float | None = None,
    max_distance_km: float | None = None,
    scheduled_start_time: datetime | None = None,
    scheduled_end_time: datetime | None = None,
    limit: int | None = None,
    service_location_id: int | None = None,
):
    providers, distance_by_provider_id = find_provider_candidates(
        matched_tags,
        service_province,
        max_price,
        latitude,
        longitude,
        max_distance_km,
        scheduled_start_time,
        scheduled_end_time,
        db,
        service_location_id=service_location_id,
    )

    recommendations = []
    schedule_enabled = (
        scheduled_start_time is not None and scheduled_end_time is not None
    )

    for provider in providers:
        recommendation = calculate_provider_match_score(
            provider,
            matched_tags,
            service_province,
            max_price,
            budget_preference,
            distance_by_provider_id.get(provider.id),
            schedule_enabled,
            db,
        )

        recommendations.append(
            {
                "provider_id": provider.id,
                "business_name": provider.business_name,
                "service_province": provider.service_province,
                "tags": provider.tags,
                "hourly_rate": provider.hourly_rate,
                "distance_km": distance_by_provider_id.get(provider.id),
                "is_available_for_requested_time": (True if schedule_enabled else None),
                "match_score": recommendation["match_score"],
                "matched_tags": recommendation["matched_tags"],
                "reason": recommendation["reason"],
                "reason_tags": recommendation["reason_tags"],
                "stats": recommendation["stats"],
                "ai_profile": build_provider_ai_profile(provider, db),
            }
        )

    recommendations.sort(
        key=lambda item: item["match_score"],
        reverse=True,
    )

    if limit is not None:
        recommendations = recommendations[:limit]

    return {
        "query": query,
        "service_province": service_province,
        "max_price": max_price,
        "latitude": latitude,
        "longitude": longitude,
        "max_distance_km": max_distance_km,
        "scheduled_start_time": (
            scheduled_start_time.isoformat() if scheduled_start_time else None
        ),
        "scheduled_end_time": (
            scheduled_end_time.isoformat() if scheduled_end_time else None
        ),
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
    }


def build_provider_ai_profile(
    provider: models.ProviderProfile,
    db: Session,
):
    stats = get_provider_ai_stats(provider.id, db)

    user = db.query(models.User).filter(models.User.id == provider.user_id).first()

    recent_reviews = (
        db.query(models.Review)
        .filter(
            models.Review.provider_profile_id == provider.id,
            models.Review.is_visible == 1,
        )
        .order_by(models.Review.created_at.desc())
        .limit(3)
        .all()
    )

    review_comments = []

    for review in recent_reviews:
        if review.comment:
            review_comments.append(review.comment)

    profile_parts = [
        f"Provider name: {user.name if user else 'Unknown'}",
        f"Business name: {provider.business_name}",
        f"Service Province: {provider.service_province}",
        f"Tags: {provider.tags}",
        f"Bio: {provider.bio}",
        f"Hourly rate: {provider.hourly_rate}",
        f"Average rating: {stats['average_rating']}",
        f"Review count: {stats['review_count']}",
        f"Completed bookings: {stats['completed_bookings']}",
        f"Complaints: {stats['complaints']}",
        f"Refunds: {stats['refunds']}",
    ]

    if review_comments:
        profile_parts.append("Recent review comments: " + " | ".join(review_comments))

    return "\n".join(profile_parts)


def build_provider_review_context(
    provider_ids: list[int],
    db: Session,
):
    review_context = []

    for provider_id in provider_ids:
        provider = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.id == provider_id)
            .first()
        )

        if not provider:
            continue

        user = db.query(models.User).filter(models.User.id == provider.user_id).first()

        positive_reviews = (
            db.query(models.Review)
            .filter(
                models.Review.provider_profile_id == provider.id,
                models.Review.is_visible == 1,
                models.Review.rating >= 4,
            )
            .order_by(models.Review.created_at.desc())
            .limit(5)
            .all()
        )

        negative_reviews = (
            db.query(models.Review)
            .filter(
                models.Review.provider_profile_id == provider.id,
                models.Review.is_visible == 1,
                models.Review.rating <= 2,
            )
            .order_by(models.Review.created_at.desc())
            .limit(5)
            .all()
        )

        review_context.append(
            {
                "provider_id": provider.id,
                "provider_name": user.name if user else "Unknown",
                "business_name": provider.business_name,
                "hourly_rate": provider.hourly_rate,
                "positive_reviews": [
                    {
                        "rating": review.rating,
                        "comment": review.comment,
                        "created_at": review.created_at,
                    }
                    for review in positive_reviews
                ],
                "negative_reviews": [
                    {
                        "rating": review.rating,
                        "comment": review.comment,
                        "created_at": review.created_at,
                    }
                    for review in negative_reviews
                ],
            }
        )

    return review_context


def enrich_review_context_with_provider_info(
    review_context: list[dict],
    db: Session,
):
    enriched_context = []

    for item in review_context:
        provider = (
            db.query(models.ProviderProfile)
            .filter(models.ProviderProfile.id == item["provider_id"])
            .first()
        )

        if not provider:
            continue

        user = db.query(models.User).filter(models.User.id == provider.user_id).first()

        enriched_context.append(
            {
                "provider_id": provider.id,
                "provider_name": user.name if user else "Unknown",
                "business_name": provider.business_name,
                "service_province": provider.service_province,
                "tags": provider.tags,
                "hourly_rate": provider.hourly_rate,
                "positive_reviews": item["positive_reviews"],
                "negative_reviews": item["negative_reviews"],
            }
        )

    return enriched_context


def has_review_context(review_context: list[dict]):
    for item in review_context:
        if item["positive_reviews"] or item["negative_reviews"]:
            return True

    return False


def get_review_documents(db: Session):
    reviews = (
        db.query(models.Review)
        .filter(
            models.Review.is_visible == 1,
            models.Review.comment.isnot(None),
        )
        .all()
    )

    documents = []

    for review in reviews:
        if not review.comment or not review.comment.strip():
            continue

        documents.append(
            {
                "review_id": review.id,
                "provider_id": review.provider_profile_id,
                "rating": review.rating,
                "comment": review.comment,
            }
        )

    return documents
