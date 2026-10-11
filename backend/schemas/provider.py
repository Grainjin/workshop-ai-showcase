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


class ProviderCertificateFileInput(BaseModel):
    file_url: str
    original_file_name: str
    content_type: str
    media_type: str = "document"
    sort_order: int = Field(default=0, ge=0)

    @field_validator("file_url", "original_file_name", "content_type")
    @classmethod
    def validate_file_fields_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Certificate file fields cannot be empty")

        return value.strip()


class ProviderProfileCreate(BaseModel):
    entity_type: str = "personal"
    business_name: str
    bio: str
    phone_number: str = ""
    address: str = ""
    service_province: str
    service_location_id: int | None = Field(default=None, gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    tags: list[str] = Field(min_length=1)
    certificate_name: str
    certificate_url: str
    certificate_files: list[ProviderCertificateFileInput] = Field(default_factory=list)
    hourly_rate: int = Field(gt=0)
    notes: str | None = None

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, value):
        if value not in {"personal", "organisation"}:
            raise ValueError("entity_type must be personal or organisation")
        return value

    @field_validator(
        "business_name",
        "bio",
        "phone_number",
        "address",
        "service_province",
        "certificate_name",
        "certificate_url",
    )
    @classmethod
    def validate_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Field cannot be empty")

        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value):
        cleaned_tags = []

        for tag in value:
            clean_tag = tag.strip()

            if not clean_tag:
                raise ValueError("Tag cannot be empty")

            if clean_tag not in ALLOWED_PROVIDER_TAGS:
                raise ValueError(f"Unsupported tag: {clean_tag}")

            if clean_tag not in cleaned_tags:
                cleaned_tags.append(clean_tag)

        return cleaned_tags


class ProviderContactProfileUpdate(BaseModel):
    phone_number: str
    address: str
    service_province: str
    service_location_id: int | None = Field(default=None, gt=0)
    notes: str | None = None

    @field_validator("phone_number", "address", "service_province")
    @classmethod
    def validate_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Field cannot be empty")

        return value.strip()


class ProviderContactProfilePatch(BaseModel):
    phone_number: str | None = None
    address: str | None = None
    service_province: str | None = None
    service_location_id: int | None = Field(default=None, gt=0)
    notes: str | None = None

    @field_validator("phone_number", "address", "service_province")
    @classmethod
    def validate_not_empty(cls, value):
        if value is None:
            return value

        if not value.strip():
            raise ValueError("Field cannot be empty")

        return value.strip()


class ProviderOperatingSettingsPatch(BaseModel):
    hourly_rate: int | None = Field(default=None, gt=0)
    service_location_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one operating setting is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Operating settings cannot be null")
        return self


class ProviderVerificationStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ProviderProfileResponse(BaseModel):
    id: int
    user_id: int
    business_name: str
    bio: str
    phone_number: str = ""
    address: str = ""
    service_province: str
    service_location_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    tags: list[str]
    certificate_name: str
    certificate_url: str
    certificate_files: list["ProviderCertificateFileResponse"] = Field(default_factory=list)
    hourly_rate: int
    verification_status: ProviderVerificationStatus
    entity_type: str = "personal"
    identity_verification_status: ProviderVerificationStatus = ProviderVerificationStatus.pending
    qualification_verification_status: ProviderVerificationStatus = ProviderVerificationStatus.pending
    verification_note: str | None = None
    notes: str | None = None
    is_online: bool = False


class ProviderProfileWithRatingResponse(ProviderProfileResponse):
    average_rating: float | None = None
    review_count: int
    distance_km: float | None = None
    is_available_for_requested_time: bool | None = None


class ProviderServiceAreaResponse(BaseModel):
    id: int
    name: str
    level: str
    label: str


class ProviderVerificationUpdate(BaseModel):
    verification_status: ProviderVerificationStatus
    verification_note: str
    verification_step: str | None = None

    @field_validator("verification_step")
    @classmethod
    def validate_verification_step(cls, value):
        if value is not None and value not in {"identity", "qualification"}:
            raise ValueError("verification_step must be identity or qualification")
        return value


class ProviderPortfolioVerificationUpdate(BaseModel):
    verification_status: ProviderVerificationStatus
    verification_note: str

    @field_validator("verification_note")
    @classmethod
    def validate_verification_note_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Verification note cannot be empty")

        return value.strip()


class ProviderAvailabilityItem(BaseModel):
    weekday: int = Field(ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None
    is_available: bool = True

    @model_validator(mode="after")
    def validate_time_range(self):
        if not self.is_available:
            if self.start_time is None:
                self.start_time = time(0, 0)
            if self.end_time is None:
                self.end_time = time(0, 0)
            return self

        if self.start_time is None or self.end_time is None:
            raise ValueError("Available day requires start_time and end_time")

        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")

        return self


class ProviderAvailabilityUpdate(BaseModel):
    availabilities: list[ProviderAvailabilityItem] = Field(min_length=0, max_length=7)

    @model_validator(mode="after")
    def validate_unique_weekdays(self):
        weekdays = [item.weekday for item in self.availabilities]

        if len(weekdays) != len(set(weekdays)):
            raise ValueError("Duplicate weekday is not allowed")

        return self


class ProviderAvailabilityResponse(BaseModel):
    id: int
    provider_profile_id: int
    weekday: int
    start_time: str
    end_time: str
    is_available: bool


class ProviderAvailabilityOverrideUpdate(BaseModel):
    start_time: time | None = None
    end_time: time | None = None
    is_available: bool = True

    @model_validator(mode="after")
    def validate_time_range(self):
        if not self.is_available:
            if self.start_time is None:
                self.start_time = time(0, 0)
            if self.end_time is None:
                self.end_time = time(0, 0)
            return self

        if self.start_time is None or self.end_time is None:
            raise ValueError("Available day requires start_time and end_time")

        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")

        return self


class ProviderAvailabilityOverrideResponse(BaseModel):
    id: int
    provider_profile_id: int
    override_date: date
    start_time: str
    end_time: str
    is_available: bool
    created_at: str
    updated_at: str


class CertificateUploadResponse(BaseModel):
    original_file_name: str
    file_name: str
    file_url: str
    content_type: str
    media_type: str = "document"
    size: int


class CertificateUploadBatchResponse(BaseModel):
    files: list[CertificateUploadResponse]


class ProviderCertificateFileResponse(BaseModel):
    id: int
    provider_profile_id: int
    file_url: str
    original_file_name: str
    content_type: str
    media_type: str = "document"
    sort_order: int
    created_at: str


class ProviderPortfolioMediaResponse(BaseModel):
    id: int
    portfolio_id: int
    file_url: str
    original_file_name: str | None = None
    content_type: str | None = None
    media_type: str = "image"
    sort_order: int
    created_at: str


class ProviderPortfolioResponse(BaseModel):
    id: int
    provider_profile_id: int
    title: str
    description: str | None = None
    image_url: str
    original_file_name: str | None = None
    content_type: str | None = None
    media_type: str = "image"
    media_items: list[ProviderPortfolioMediaResponse] = Field(default_factory=list)
    verification_status: ProviderVerificationStatus = ProviderVerificationStatus.pending
    verification_note: str | None = None
    created_at: str


ProviderProfileResponse.model_rebuild()
ProviderProfileWithRatingResponse.model_rebuild()
