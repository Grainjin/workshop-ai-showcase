from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Query, Session

from backend import models
from backend.utils.availability import (
    is_provider_available_for_datetime_range,
    is_provider_open_now,
)
from backend.utils.formatters import normalize_provider_tags, tags_to_list
from backend.utils.location import (
    calculate_distance_km,
    has_location,
    has_partial_location,
)
from backend.utils.pagination import paginate_list, paginate_query
from backend.utils.review import get_provider_rating_summary


SORT_ALIASES = {
    "nearest": "distance_asc",
    "lowest_price": "price_asc",
    "highest_rating": "rating_desc",
}


@dataclass
class ProviderSearchResult:
    profiles: list[models.ProviderProfile]
    total: int
    page: int
    page_size: int
    distance_by_provider_id: dict[int, float]
    is_open_by_provider_id: dict[int, bool]
    schedule_enabled: bool


def normalize_provider_sort(sort_by: str | None):
    return SORT_ALIASES.get(sort_by, sort_by)


def validate_provider_search_params(
    latitude: float | None,
    longitude: float | None,
    max_distance_km: float | None,
    scheduled_start_time: datetime | None,
    scheduled_end_time: datetime | None,
    sort_by: str | None,
):
    if has_partial_location(latitude, longitude):
        raise HTTPException(
            status_code=400,
            detail="Latitude and longitude must be provided together",
        )

    location_enabled = has_location(latitude, longitude)
    normalized_sort = normalize_provider_sort(sort_by)

    if max_distance_km is not None and not location_enabled:
        raise HTTPException(
            status_code=400,
            detail="max_distance_km requires latitude and longitude",
        )

    if normalized_sort in {"distance_asc", "distance_desc"} and not location_enabled:
        raise HTTPException(
            status_code=400,
            detail="Distance sorting requires latitude and longitude",
        )

    if (scheduled_start_time is None) != (scheduled_end_time is None):
        raise HTTPException(
            status_code=400,
            detail="scheduled_start_time and scheduled_end_time must be provided together",
        )

    if (
        scheduled_start_time is not None
        and scheduled_end_time is not None
        and scheduled_end_time <= scheduled_start_time
    ):
        raise HTTPException(
            status_code=400,
            detail="scheduled_end_time must be after scheduled_start_time",
        )

    return location_enabled, normalized_sort


def filter_provider_profiles(
    query: Query,
    db: Session,
    *,
    tags: list[str] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    max_distance_km: float | None = None,
    scheduled_start_time: datetime | None = None,
    scheduled_end_time: datetime | None = None,
    min_rating: float | None = None,
    is_open: bool | None = None,
    sort_by: str | None = None,
    page: int = 1,
    page_size: int = 20,
    existing_distance_by_provider_id: dict[int, float | None] | None = None,
    include_is_open: bool = False,
):
    location_enabled, normalized_sort = validate_provider_search_params(
        latitude,
        longitude,
        max_distance_km,
        scheduled_start_time,
        scheduled_end_time,
        sort_by,
    )
    schedule_enabled = (
        scheduled_start_time is not None and scheduled_end_time is not None
    )
    sql_sort_supported = {
        None,
        "price_asc",
        "price_desc",
    }
    can_use_sql_pagination = (
        not tags
        and not location_enabled
        and not schedule_enabled
        and min_rating is None
        and is_open is None
        and existing_distance_by_provider_id is None
        and not include_is_open
        and normalized_sort in sql_sort_supported
    )
    if can_use_sql_pagination:
        if normalized_sort == "price_asc":
            query = query.order_by(models.ProviderProfile.hourly_rate.asc())
        elif normalized_sort == "price_desc":
            query = query.order_by(models.ProviderProfile.hourly_rate.desc())

        profiles, total, normalized_page, normalized_page_size = paginate_query(
            query,
            page,
            page_size,
        )
        return ProviderSearchResult(
            profiles=profiles,
            total=total,
            page=normalized_page,
            page_size=normalized_page_size,
            distance_by_provider_id={},
            is_open_by_provider_id={},
            schedule_enabled=False,
        )

    return filter_provider_profile_list(
        query.all(),
        db,
        tags=tags,
        latitude=latitude,
        longitude=longitude,
        max_distance_km=max_distance_km,
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
        min_rating=min_rating,
        is_open=is_open,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
        existing_distance_by_provider_id=existing_distance_by_provider_id,
        include_is_open=include_is_open,
    )


def filter_provider_profile_list(
    profiles: list[models.ProviderProfile],
    db: Session,
    *,
    tags: list[str] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    max_distance_km: float | None = None,
    scheduled_start_time: datetime | None = None,
    scheduled_end_time: datetime | None = None,
    min_rating: float | None = None,
    is_open: bool | None = None,
    sort_by: str | None = None,
    page: int = 1,
    page_size: int = 20,
    existing_distance_by_provider_id: dict[int, float | None] | None = None,
    include_is_open: bool = False,
):
    location_enabled, normalized_sort = validate_provider_search_params(
        latitude,
        longitude,
        max_distance_km,
        scheduled_start_time,
        scheduled_end_time,
        sort_by,
    )
    schedule_enabled = (
        scheduled_start_time is not None and scheduled_end_time is not None
    )

    normalized_tags = normalize_provider_tags(tags or [])
    if tags and not normalized_tags:
        profiles = []
    elif normalized_tags:
        profiles = [
            profile
            for profile in profiles
            if all(tag in tags_to_list(profile.tags) for tag in normalized_tags)
        ]

    distance_by_provider_id: dict[int, float] = {}
    is_open_by_provider_id: dict[int, bool] = {}
    rating_by_provider_id: dict[int, dict] = {}
    filtered_profiles: list[models.ProviderProfile] = []

    for profile in profiles:
        if schedule_enabled and not is_provider_available_for_datetime_range(
            profile.id,
            scheduled_start_time,
            scheduled_end_time,
            db,
        ):
            continue

        if min_rating is not None or normalized_sort == "rating_desc":
            rating = get_provider_rating_summary(profile.id, db)
            rating_by_provider_id[profile.id] = rating
            if min_rating is not None and (
                rating["average_rating"] is None
                or rating["average_rating"] < min_rating
            ):
                continue

        if is_open is not None or include_is_open:
            provider_is_open = is_provider_open_now(profile.id, db)
            is_open_by_provider_id[profile.id] = provider_is_open
            if is_open is not None and provider_is_open != is_open:
                continue

        if location_enabled:
            if existing_distance_by_provider_id is not None:
                distance_km = existing_distance_by_provider_id.get(profile.id)
                if distance_km is None:
                    continue
            else:
                if not has_location(profile.latitude, profile.longitude):
                    continue
                distance_km = calculate_distance_km(
                    latitude,
                    longitude,
                    profile.latitude,
                    profile.longitude,
                )

            if max_distance_km is not None and distance_km > max_distance_km:
                continue
            distance_by_provider_id[profile.id] = distance_km

        filtered_profiles.append(profile)

    if normalized_sort == "distance_asc":
        filtered_profiles.sort(
            key=lambda profile: (
                distance_by_provider_id[profile.id],
                profile.id,
            )
        )
    elif normalized_sort == "distance_desc":
        filtered_profiles.sort(
            key=lambda profile: (
                distance_by_provider_id[profile.id],
                -profile.id,
            ),
            reverse=True,
        )
    elif normalized_sort == "price_asc":
        filtered_profiles.sort(key=lambda profile: (profile.hourly_rate, profile.id))
    elif normalized_sort == "price_desc":
        filtered_profiles.sort(
            key=lambda profile: (profile.hourly_rate, -profile.id),
            reverse=True,
        )
    elif normalized_sort == "rating_desc":
        filtered_profiles.sort(
            key=lambda profile: (
                rating_by_provider_id.get(profile.id, {}).get("average_rating") or -1,
                rating_by_provider_id.get(profile.id, {}).get("review_count") or 0,
                -profile.hourly_rate,
                -profile.id,
            ),
            reverse=True,
        )

    paginated_profiles, total, normalized_page, normalized_page_size = paginate_list(
        filtered_profiles,
        page,
        page_size,
    )
    return ProviderSearchResult(
        profiles=paginated_profiles,
        total=total,
        page=normalized_page,
        page_size=normalized_page_size,
        distance_by_provider_id=distance_by_provider_id,
        is_open_by_provider_id=is_open_by_provider_id,
        schedule_enabled=schedule_enabled,
    )
