import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.schemas import ProviderVerificationStatus
from backend.utils.formatters import tags_to_list
from backend.utils.location import calculate_distance_km, has_location
from backend.utils.provider_search import (
    filter_provider_profile_list,
    normalize_provider_sort,
    validate_provider_search_params,
)
from backend.utils.service_locations import (
    filter_provider_query_by_location,
    normalize_location_name,
    resolve_location_context,
)
from backend.utils.provider import format_provider_profile_with_rating
from backend.core.clock import utc_now

DEFAULT_HISTORY_PROVIDER_TAG = "cleaning"
SEARCH_SPLIT_PATTERN = re.compile(r"[\s,.;:/\\|]+")


def get_customer_search_history(customer_id: int, db: Session):
    return (
        db.query(models.CustomerSearchHistory)
        .filter(models.CustomerSearchHistory.customer_id == customer_id)
        .first()
    )


def get_customer_history_tag(customer_id: int, db: Session):
    history = get_customer_search_history(customer_id, db)

    if history and history.last_provider_tag:
        return history.last_provider_tag

    return DEFAULT_HISTORY_PROVIDER_TAG


def save_customer_provider_tag_history(
    customer_id: int,
    provider_profile: models.ProviderProfile,
    db: Session,
):
    provider_tags = tags_to_list(provider_profile.tags)
    last_provider_tag = (
        provider_tags[0] if provider_tags else DEFAULT_HISTORY_PROVIDER_TAG
    )
    history = get_customer_search_history(customer_id, db)
    now = utc_now()

    if not history:
        history = models.CustomerSearchHistory(
            customer_id=customer_id,
            last_provider_profile_id=provider_profile.id,
            last_provider_tag=last_provider_tag,
            updated_at=now,
        )
        db.add(history)
    else:
        history.last_provider_profile_id = provider_profile.id
        history.last_provider_tag = last_provider_tag
        history.updated_at = now

    db.commit()
    db.refresh(history)
    return history


def get_customer_recommendation_location(customer_profile):
    if not customer_profile:
        return None, None

    if has_location(
        customer_profile.current_latitude, customer_profile.current_longitude
    ):
        return customer_profile.current_latitude, customer_profile.current_longitude

    if has_location(
        customer_profile.default_service_latitude,
        customer_profile.default_service_longitude,
    ):
        return (
            customer_profile.default_service_latitude,
            customer_profile.default_service_longitude,
        )

    if has_location(customer_profile.latitude, customer_profile.longitude):
        return customer_profile.latitude, customer_profile.longitude

    return None, None


def get_first_provider_portfolio_image_url(provider_profile_id: int, db: Session):
    portfolio = (
        db.query(models.ProviderPortfolio)
        .filter(
            models.ProviderPortfolio.provider_profile_id == provider_profile_id,
            models.ProviderPortfolio.media_type == "image",
            models.ProviderPortfolio.verification_status == "approved",
        )
        .order_by(models.ProviderPortfolio.created_at.asc())
        .first()
    )

    return portfolio.image_url if portfolio else None


def format_home_provider_item(
    provider_profile: models.ProviderProfile,
    db: Session,
    recommendation_score: float,
    matched_tags: list[str],
    recommendation_reasons: list[str],
    distance_km: float | None,
):
    provider_data = format_provider_profile_with_rating(provider_profile, db)
    provider_data["first_portfolio_image_url"] = get_first_provider_portfolio_image_url(
        provider_profile.id,
        db,
    )
    provider_data["recommendation_score"] = recommendation_score
    provider_data["matched_tags"] = matched_tags
    provider_data["recommendation_reasons"] = recommendation_reasons
    provider_data["distance_km"] = distance_km

    return provider_data


def calculate_home_recommendation_score(
    provider_profile: models.ProviderProfile,
    service_province: str,
    history_provider_tag: str,
    customer_latitude: float | None,
    customer_longitude: float | None,
    selected_provider_tag: str | None = None,
):
    score = 0.0
    reasons = []
    distance_km = None
    provider_tags = tags_to_list(provider_profile.tags)
    recommendation_tag = selected_provider_tag or history_provider_tag

    if normalize_location_name(provider_profile.service_province) == normalize_location_name(
        service_province
    ):
        score += 100
        reasons.append("same_province")

    if recommendation_tag in provider_tags:
        score += 45
        reasons.append(
            "matched_selected_tag" if selected_provider_tag else "matched_history_tag"
        )

    if has_location(customer_latitude, customer_longitude) and has_location(
        provider_profile.latitude,
        provider_profile.longitude,
    ):
        distance_km = calculate_distance_km(
            customer_latitude,
            customer_longitude,
            provider_profile.latitude,
            provider_profile.longitude,
        )
        distance_score = max(0, 30 - distance_km)
        score += distance_score

        if distance_score > 0:
            reasons.append("nearby")

    return {
        "score": round(score, 2),
        "distance_km": distance_km,
        "matched_tags": (
            [recommendation_tag] if recommendation_tag in provider_tags else []
        ),
        "reason_codes": reasons,
    }


def build_customer_home_recommendations(
    current_user: models.User,
    db: Session,
    service_province: str | None = None,
    service_location_id: int | None = None,
    provider_tag: str | None = None,
    limit: int = 20,
):
    customer_profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )
    selected_province, selected_location_id = resolve_location_context(
        db,
        requested_province=service_province,
        requested_location_id=service_location_id,
        profile_province=(
            customer_profile.service_province if customer_profile else None
        ),
        profile_location_id=(
            customer_profile.service_location_id if customer_profile else None
        ),
    )
    location_filter_province = selected_province
    selected_province = selected_province or "Istanbul"
    history_provider_tag = get_customer_history_tag(current_user.id, db)
    customer_latitude, customer_longitude = get_customer_recommendation_location(
        customer_profile
    )

    provider_query = db.query(models.ProviderProfile)
    provider_query = filter_provider_query_by_location(
        provider_query,
        db,
        location_id=selected_location_id,
        province_name=location_filter_province,
    )
    provider_profiles = provider_query.all()

    recommendations = []
    for profile in provider_profiles:
        profile_tags = tags_to_list(profile.tags)
        if provider_tag and provider_tag not in profile_tags:
            continue

        scoring = calculate_home_recommendation_score(
            profile,
            selected_province,
            history_provider_tag,
            customer_latitude,
            customer_longitude,
            selected_provider_tag=provider_tag,
        )
        recommendations.append(
            format_home_provider_item(
                profile,
                db,
                scoring["score"],
                scoring["matched_tags"],
                scoring["reason_codes"],
                scoring["distance_km"],
            )
        )

    recommendations.sort(
        key=lambda provider: (
            provider["recommendation_score"],
            provider.get("average_rating") or 0,
            provider.get("review_count") or 0,
            -provider.get("hourly_rate", 0),
        ),
        reverse=True,
    )

    return {
        "service_province": selected_province,
        "service_location_id": selected_location_id,
        "history_provider_tag": history_provider_tag,
        "items": recommendations[:limit],
    }


def tokenize_provider_search_keyword(keyword: str):
    tokens = [
        token.strip().lower()
        for token in SEARCH_SPLIT_PATTERN.split(keyword)
        if token.strip()
    ]

    return list(dict.fromkeys(tokens))


def text_matches_token(text: str | None, token: str):
    if not text:
        return False

    normalized_text = text.lower()
    return token in normalized_text or normalized_text in token


def score_provider_search_match(
    provider_profile: models.ProviderProfile,
    tokens: list[str],
    service_province: str,
    customer_latitude: float | None,
    customer_longitude: float | None,
):
    score = 0.0
    matched_tags = []
    reasons = []
    matched_any_search_field = False
    provider_tags = tags_to_list(provider_profile.tags)
    searchable_tags = [tag.lower() for tag in provider_tags]

    for token in tokens:
        tag_matched = [
            provider_tags[index]
            for index, tag in enumerate(searchable_tags)
            if token in tag or tag in token
        ]
        if tag_matched:
            matched_any_search_field = True
            score += 80 * len(tag_matched)
            reasons.append("matched_tag")
            matched_tags.extend(tag for tag in tag_matched if tag not in matched_tags)

        if text_matches_token(provider_profile.business_name, token):
            matched_any_search_field = True
            score += 45
            reasons.append("matched_business_name")

        if text_matches_token(provider_profile.service_province, token):
            matched_any_search_field = True
            score += 35
            reasons.append("matched_province_keyword")

    if not matched_any_search_field:
        return None

    if normalize_location_name(provider_profile.service_province) == normalize_location_name(
        service_province
    ):
        score += 60
        reasons.append("same_province")

    distance_km = None
    if has_location(customer_latitude, customer_longitude) and has_location(
        provider_profile.latitude,
        provider_profile.longitude,
    ):
        distance_km = calculate_distance_km(
            customer_latitude,
            customer_longitude,
            provider_profile.latitude,
            provider_profile.longitude,
        )
        distance_score = max(0, 25 - distance_km)
        score += distance_score

        if distance_score > 0:
            reasons.append("nearby")

    return {
        "score": round(score, 2),
        "distance_km": distance_km,
        "matched_tags": matched_tags,
        "reason_codes": list(dict.fromkeys(reasons)),
    }


def search_customer_providers(
    current_user: models.User,
    db: Session,
    keyword: str,
    service_province: str | None = None,
    service_location_id: int | None = None,
    limit: int = 40,
    min_price: int | None = None,
    max_price: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    max_distance_km: float | None = None,
    scheduled_start_time: datetime | None = None,
    scheduled_end_time: datetime | None = None,
    tags: list[str] | None = None,
    sort_by: str | None = None,
    min_rating: float | None = None,
    is_open: bool | None = None,
):
    tokens = tokenize_provider_search_keyword(keyword)
    customer_profile = (
        db.query(models.CustomerProfile)
        .filter(models.CustomerProfile.user_id == current_user.id)
        .first()
    )
    selected_province = (
        service_province
        or (customer_profile.service_province if customer_profile else None)
        or "Istanbul"
    )
    customer_latitude, customer_longitude = get_customer_recommendation_location(
        customer_profile
    )

    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=400,
            detail="Latitude and longitude must be provided together",
        )

    effective_latitude = (
        latitude if latitude is not None else customer_latitude
    )
    effective_longitude = (
        longitude if longitude is not None else customer_longitude
    )

    normalized_sort = normalize_provider_sort(sort_by)
    filter_latitude = latitude
    filter_longitude = longitude
    distance_operation_requested = (
        max_distance_km is not None
        or normalized_sort in {"distance_asc", "distance_desc"}
    )
    if distance_operation_requested and not has_location(
        filter_latitude,
        filter_longitude,
    ):
        filter_latitude = effective_latitude
        filter_longitude = effective_longitude

    validate_provider_search_params(
        filter_latitude,
        filter_longitude,
        max_distance_km,
        scheduled_start_time,
        scheduled_end_time,
        sort_by,
    )

    if not tokens:
        return {
            "keyword": keyword,
            "tokens": [],
            "service_province": selected_province,
            "service_location_id": service_location_id,
            "items": [],
        }

    provider_query = db.query(models.ProviderProfile).filter(
        models.ProviderProfile.qualification_verification_status
        == ProviderVerificationStatus.approved
    )
    provider_query = filter_provider_query_by_location(
        provider_query,
        db,
        location_id=service_location_id,
        province_name=service_province,
    )
    if min_price is not None:
        provider_query = provider_query.filter(
            models.ProviderProfile.hourly_rate >= min_price
        )
    if max_price is not None:
        provider_query = provider_query.filter(
            models.ProviderProfile.hourly_rate <= max_price
        )
    provider_profiles = provider_query.all()

    keyword_matches = []
    scoring_by_provider_id = {}
    for profile in provider_profiles:
        scoring = score_provider_search_match(
            profile,
            tokens,
            selected_province,
            effective_latitude,
            effective_longitude,
        )
        if not scoring:
            continue

        keyword_matches.append(profile)
        scoring_by_provider_id[profile.id] = scoring

    filter_page_size = limit if sort_by is not None else max(len(keyword_matches), 1)
    search_result = filter_provider_profile_list(
        keyword_matches,
        db,
        tags=tags,
        latitude=filter_latitude,
        longitude=filter_longitude,
        max_distance_km=max_distance_km,
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
        min_rating=min_rating,
        is_open=is_open,
        sort_by=sort_by,
        page=1,
        page_size=filter_page_size,
        existing_distance_by_provider_id={
            profile_id: scoring["distance_km"]
            for profile_id, scoring in scoring_by_provider_id.items()
        },
        include_is_open=True,
    )

    provider_user_ids = {profile.user_id for profile in search_result.profiles}
    avatar_url_by_user_id = {
        user.id: user.avatar_url
        for user in db.query(models.User)
        .filter(models.User.id.in_(provider_user_ids))
        .all()
    }

    results = []
    for profile in search_result.profiles:
        scoring = scoring_by_provider_id[profile.id]

        provider_data = format_home_provider_item(
            profile,
            db,
            scoring["score"],
            scoring["matched_tags"],
            scoring["reason_codes"],
            search_result.distance_by_provider_id.get(
                profile.id,
                scoring["distance_km"],
            ),
        )
        provider_data["avatar_url"] = avatar_url_by_user_id.get(profile.user_id)
        provider_data["is_open"] = search_result.is_open_by_provider_id[profile.id]
        results.append(provider_data)

    if sort_by is None:
        results.sort(
            key=lambda provider: (
                provider["recommendation_score"],
                provider.get("average_rating") or 0,
                provider.get("review_count") or 0,
                -provider.get("hourly_rate", 0),
            ),
            reverse=True,
        )
        results = results[:limit]

    return {
        "keyword": keyword,
        "tokens": tokens,
        "service_province": selected_province,
        "service_location_id": service_location_id,
        "items": results,
    }
