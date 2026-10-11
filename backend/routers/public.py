"""Public API.

Unauthenticated data: approved providers, public profiles, reviews, portfolios, ratings.
"""

from datetime import datetime

from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from backend import models
from backend.auth import get_db
from backend.utils.formatters import format_provider_portfolio_response
from backend.utils.pagination import (
    build_paginated_response,
    paginate_query,
)
from backend.utils.provider import format_provider_profile_with_rating
from backend.utils.provider_search import filter_provider_profiles
from backend.utils.service_locations import (
    filter_provider_query_by_location,
    format_location_response,
    get_location,
)
from backend.utils.review import (
    format_review_detail_response,
    get_provider_rating_summary as build_provider_rating_summary,
)
from backend.schemas import (
    ApiResponse,
    PaginatedData,
    ProviderProfileWithRatingResponse,
    ProviderPortfolioResponse,
    ProviderVerificationStatus,
    RatingSummaryResponse,
    ReviewDetailResponse,
    PlaceDetailsResponse,
    PlacesAutocompleteResponse,
    ServiceLocationListResponse,
    ServiceLocationResponse,
)
from backend.services.places_service import (
    autocomplete as places_autocomplete,
    enforce_rate_limit,
    get_details as get_place_details,
    require_places_api_key,
)
from backend.utils.response import success_response
from backend.utils.router import ApiRouter

router = ApiRouter(tags=["Public"])


@router.get(
    "/locations",
    response_model=ApiResponse[ServiceLocationListResponse],
)
def get_service_locations(
    parent_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    if parent_id is not None:
        parent = db.query(models.ServiceLocation).filter(
            models.ServiceLocation.id == parent_id
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Service location not found")

    locations = (
        db.query(models.ServiceLocation)
        .filter(models.ServiceLocation.parent_id == parent_id)
        .order_by(models.ServiceLocation.name.asc(), models.ServiceLocation.id.asc())
        .all()
    )
    return success_response({"items": [format_location_response(item) for item in locations]})


@router.get(
    "/locations/{location_id}",
    response_model=ApiResponse[ServiceLocationResponse],
)
def get_service_location(location_id: int, db: Session = Depends(get_db)):
    return success_response(format_location_response(get_location(db, location_id)))


@router.get(
    "/places/autocomplete",
    response_model=ApiResponse[PlacesAutocompleteResponse],
    responses={429: {"description": "Places rate limit exceeded"}},
)
def autocomplete_places(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
):
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    require_places_api_key()
    enforce_rate_limit(request.client.host if request.client else "unknown")
    return success_response(places_autocomplete(query))


@router.get(
    "/places/details",
    response_model=ApiResponse[PlaceDetailsResponse],
    responses={429: {"description": "Places rate limit exceeded"}},
)
def details_for_place(
    request: Request,
    place_id: str = Query(..., min_length=1, max_length=256),
):
    selected_place_id = place_id.strip()
    if not selected_place_id:
        raise HTTPException(status_code=422, detail="Place ID cannot be empty")

    require_places_api_key()
    enforce_rate_limit(request.client.host if request.client else "unknown")
    return success_response(get_place_details(selected_place_id))


@router.get(
    "/providers",
    response_model=ApiResponse[PaginatedData[ProviderProfileWithRatingResponse]],
)
def get_all_providers(
    service_province: str | None = None,
    service_location_id: int | None = Query(default=None, gt=0),
    min_price: int | None = None,
    max_price: int | None = None,
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    max_distance_km: float | None = Query(default=None, gt=0),
    scheduled_start_time: datetime | None = None,
    scheduled_end_time: datetime | None = None,
    tags: list[str] | None = Query(default=None),
    sort_by: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
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
    if min_price is not None:
        query = query.filter(models.ProviderProfile.hourly_rate >= min_price)
    if max_price is not None:
        query = query.filter(models.ProviderProfile.hourly_rate <= max_price)

    search_result = filter_provider_profiles(
        query,
        db,
        tags=tags,
        latitude=latitude,
        longitude=longitude,
        max_distance_km=max_distance_km,
        scheduled_start_time=scheduled_start_time,
        scheduled_end_time=scheduled_end_time,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )

    result = []
    for profile in search_result.profiles:
        provider_result = format_provider_profile_with_rating(profile, db)
        if profile.id in search_result.distance_by_provider_id:
            provider_result["distance_km"] = search_result.distance_by_provider_id[
                profile.id
            ]
        if search_result.schedule_enabled:
            provider_result["is_available_for_requested_time"] = True
        result.append(provider_result)
    return success_response(
        build_paginated_response(
            result,
            search_result.total,
            search_result.page,
            search_result.page_size,
        )
    )


@router.get(
    "/providers/{provider_id}",
    response_model=ApiResponse[ProviderProfileWithRatingResponse],
)
def get_provider_by_id(provider_id: int, db: Session = Depends(get_db)):
    profile = (
        db.query(models.ProviderProfile)
        .filter(
            models.ProviderProfile.id == provider_id,
            models.ProviderProfile.qualification_verification_status
            == ProviderVerificationStatus.approved,
        )
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Provider not found")
    return success_response(format_provider_profile_with_rating(profile, db))


@router.get(
    "/providers/{provider_id}/reviews",
    response_model=ApiResponse[PaginatedData[ReviewDetailResponse]],
)
def get_provider_reviews(
    provider_id: int, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)
):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(
            models.ProviderProfile.id == provider_id,
            models.ProviderProfile.qualification_verification_status
            == ProviderVerificationStatus.approved,
        )
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider not found")
    query = (
        db.query(models.Review)
        .filter(
            models.Review.provider_profile_id == provider_id,
            models.Review.is_visible == 1,
        )
        .order_by(models.Review.created_at.desc())
    )
    reviews, total, page, page_size = paginate_query(query, page, page_size)
    result = []
    for review in reviews:
        result.append(format_review_detail_response(review, db))
    return build_paginated_response(result, total, page, page_size)


@router.get(
    "/providers/{provider_id}/portfolio",
    response_model=ApiResponse[PaginatedData[ProviderPortfolioResponse]],
)
def get_provider_public_portfolio(
    provider_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(
            models.ProviderProfile.id == provider_id,
            models.ProviderProfile.qualification_verification_status
            == ProviderVerificationStatus.approved,
        )
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider not found")

    query = (
        db.query(models.ProviderPortfolio)
        .filter(
            models.ProviderPortfolio.provider_profile_id == provider_id,
            models.ProviderPortfolio.verification_status
            == ProviderVerificationStatus.approved,
        )
        .order_by(models.ProviderPortfolio.created_at.desc())
    )
    portfolios, total, page, page_size = paginate_query(query, page, page_size)
    result = [
        format_provider_portfolio_response(portfolio, db) for portfolio in portfolios
    ]
    return build_paginated_response(result, total, page, page_size)


@router.get(
    "/providers/{provider_id}/portfolio/{portfolio_id}",
    response_model=ApiResponse[ProviderPortfolioResponse],
)
def get_provider_public_portfolio_item(
    provider_id: int,
    portfolio_id: int,
    db: Session = Depends(get_db),
):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(
            models.ProviderProfile.id == provider_id,
            models.ProviderProfile.qualification_verification_status
            == ProviderVerificationStatus.approved,
        )
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider not found")

    portfolio = (
        db.query(models.ProviderPortfolio)
        .filter(
            models.ProviderPortfolio.id == portfolio_id,
            models.ProviderPortfolio.provider_profile_id == provider_id,
            models.ProviderPortfolio.verification_status
            == ProviderVerificationStatus.approved,
        )
        .first()
    )
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    return success_response(format_provider_portfolio_response(portfolio, db))


@router.get(
    "/providers/{provider_id}/rating-summary",
    response_model=ApiResponse[RatingSummaryResponse],
)
def get_provider_rating_summary(provider_id: int, db: Session = Depends(get_db)):
    provider_profile = (
        db.query(models.ProviderProfile)
        .filter(
            models.ProviderProfile.id == provider_id,
            models.ProviderProfile.qualification_verification_status
            == ProviderVerificationStatus.approved,
        )
        .first()
    )
    if not provider_profile:
        raise HTTPException(status_code=404, detail="Provider not found")
    summary = build_provider_rating_summary(provider_id, db)
    summary["provider_profile_id"] = provider_id
    return success_response(summary)


@router.get("/reviews/{review_id}", response_model=ApiResponse[ReviewDetailResponse])
def get_review_by_id(review_id: int, db: Session = Depends(get_db)):
    review = (
        db.query(models.Review)
        .filter(models.Review.id == review_id, models.Review.is_visible == 1)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return success_response(format_review_detail_response(review, db))
