from datetime import date, datetime, time
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from backend.constants import ALLOWED_PROVIDER_TAGS

from backend.schemas.common import *  # noqa: F403
from backend.schemas.provider import (
    ProviderProfileWithRatingResponse,
    ProviderServiceAreaResponse,
)


class CustomerProfileCreate(BaseModel):
    phone_number: str
    address: str
    service_province: str
    service_location_id: int | None = Field(default=None, gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    current_address: str | None = None
    current_latitude: float | None = Field(default=None, ge=-90, le=90)
    current_longitude: float | None = Field(default=None, ge=-180, le=180)
    default_service_address: str | None = None
    default_service_latitude: float | None = Field(default=None, ge=-90, le=90)
    default_service_longitude: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = None

    @field_validator(
        "phone_number",
        "address",
        "service_province",
        "current_address",
        "default_service_address",
    )
    @classmethod
    def validate_not_empty(cls, value):
        if value is None:
            return value

        if not value.strip():
            raise ValueError("Field cannot be empty")

        return value


class CustomerProfilePatch(BaseModel):
    phone_number: str | None = None
    address: str | None = None
    service_province: str | None = None
    service_location_id: int | None = Field(default=None, gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    current_address: str | None = None
    current_latitude: float | None = Field(default=None, ge=-90, le=90)
    current_longitude: float | None = Field(default=None, ge=-180, le=180)
    default_service_address: str | None = None
    default_service_latitude: float | None = Field(default=None, ge=-90, le=90)
    default_service_longitude: float | None = Field(default=None, ge=-180, le=180)
    notes: str | None = None

    @field_validator(
        "phone_number",
        "address",
        "service_province",
        "current_address",
        "default_service_address",
    )
    @classmethod
    def validate_not_empty(cls, value):
        if value is None:
            return value

        if not value.strip():
            raise ValueError("Field cannot be empty")

        return value.strip()


class CustomerServiceProvinceUpdate(BaseModel):
    service_province: str
    service_location_id: int | None = Field(default=None, gt=0)

    @field_validator("service_province")
    @classmethod
    def validate_service_province_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Field cannot be empty")

        return value.strip()


class CustomerSearchHistoryResponse(BaseModel):
    id: int
    customer_id: int
    last_provider_profile_id: int | None = None
    last_provider_tag: str
    updated_at: str


class HomeProviderRecommendationResponse(ProviderProfileWithRatingResponse):
    first_portfolio_image_url: str | None = None
    recommendation_score: float
    matched_tags: list[str] = Field(default_factory=list)
    recommendation_reasons: list[str] = Field(default_factory=list)


class CustomerHomeRecommendationResponseData(BaseModel):
    service_province: str
    service_location_id: int | None = None
    history_provider_tag: str
    items: list[HomeProviderRecommendationResponse]


class CustomerProviderSearchItemResponse(HomeProviderRecommendationResponse):
    avatar_url: str | None = None
    is_open: bool


class CustomerProviderSearchResponseData(BaseModel):
    keyword: str
    tokens: list[str]
    service_province: str
    service_location_id: int | None = None
    items: list[CustomerProviderSearchItemResponse]


class CustomerProviderDetailProviderResponse(ProviderProfileWithRatingResponse):
    is_open: bool
    is_favorited: bool
    service_areas: list[ProviderServiceAreaResponse] = Field(default_factory=list)


class CustomerProviderDetailResponseData(BaseModel):
    provider: CustomerProviderDetailProviderResponse
    history: CustomerSearchHistoryResponse


HomeProviderRecommendationResponse.model_rebuild()
CustomerHomeRecommendationResponseData.model_rebuild()
CustomerProviderSearchResponseData.model_rebuild()
CustomerProviderDetailResponseData.model_rebuild()
