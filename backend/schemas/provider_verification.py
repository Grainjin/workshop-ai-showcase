from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.constants import ALLOWED_PROVIDER_TAGS


class VerificationApplicationStatus(str, Enum):
    not_submitted = "not_submitted"
    locked = "locked"
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class IdentityDocumentType(str, Enum):
    national_id = "national_id"
    passport = "passport"


class VerificationDecision(BaseModel):
    status: str
    review_note: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in {"approved", "rejected"}:
            raise ValueError("status must be approved or rejected")
        return value

    @model_validator(mode="after")
    def require_rejection_note(self):
        if self.status == "rejected" and not (self.review_note or "").strip():
            raise ValueError("review_note is required when rejecting an application")
        if self.review_note is not None:
            self.review_note = self.review_note.strip() or None
        return self


class VerificationFileInput(BaseModel):
    file_url: str
    original_file_name: str
    content_type: str

    @field_validator("file_url", "original_file_name", "content_type")
    @classmethod
    def non_empty(cls, value):
        if not value.strip():
            raise ValueError("File fields cannot be empty")
        return value.strip()


class QualificationVerificationSubmit(BaseModel):
    entity_type: str
    legal_name: str | None = None
    unique_enterprise_id: str | None = None
    description: str
    contact_phone: str
    business_address: str
    business_place_id: str | None = None
    business_latitude: float = Field(ge=-90, le=90)
    business_longitude: float = Field(ge=-180, le=180)
    service_categories: list[str] = Field(min_length=1)
    service_location_ids: list[int] = Field(min_length=1)
    qualification_files: list[VerificationFileInput] = Field(min_length=1, max_length=5)

    @field_validator("description", "contact_phone", "business_address")
    @classmethod
    def required_text(cls, value):
        if not value.strip():
            raise ValueError("Field cannot be empty")
        return value.strip()

    @field_validator("service_categories")
    @classmethod
    def valid_services(cls, values):
        cleaned = []
        for value in values:
            service = value.strip()
            if service not in ALLOWED_PROVIDER_TAGS:
                raise ValueError(f"Unsupported service category: {service}")
            if service not in cleaned:
                cleaned.append(service)
        return cleaned

    @field_validator("service_location_ids")
    @classmethod
    def unique_positive_location_ids(cls, values):
        if any(value <= 0 for value in values):
            raise ValueError("service_location_ids must be positive")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate service locations are not allowed")
        return values

    @model_validator(mode="after")
    def validate_entity_fields(self):
        if self.entity_type not in {"personal", "organisation"}:
            raise ValueError("entity_type must be personal or organisation")
        if self.entity_type == "organisation":
            if not (self.legal_name or "").strip():
                raise ValueError("legal_name is required for an organisation")
            if not (self.unique_enterprise_id or "").strip():
                raise ValueError("unique_enterprise_id is required for an organisation")
            self.legal_name = self.legal_name.strip()
            self.unique_enterprise_id = self.unique_enterprise_id.strip().upper()
        else:
            if self.legal_name is not None or self.unique_enterprise_id is not None:
                raise ValueError(
                    "Personal providers cannot submit legal_name or unique_enterprise_id"
                )
        return self


class ProviderOperatingSettingsV2Patch(BaseModel):
    description: str | None = None
    contact_phone: str | None = None
    business_address: str | None = None
    business_place_id: str | None = None
    business_latitude: float | None = Field(default=None, ge=-90, le=90)
    business_longitude: float | None = Field(default=None, ge=-180, le=180)
    hourly_rate: int | None = Field(default=None, gt=0)
    enabled_service_categories: list[str] | None = None

    @field_validator("description", "contact_phone", "business_address")
    @classmethod
    def non_empty_text(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Operating setting cannot be blank")
        return value.strip() if value is not None else value

    @field_validator("enabled_service_categories")
    @classmethod
    def unique_services(cls, values):
        if values is None:
            return values
        cleaned = []
        for value in values:
            service = value.strip()
            if not service:
                raise ValueError("Service category cannot be blank")
            if service not in cleaned:
                cleaned.append(service)
        return cleaned

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one operating setting is required")
        nullable_fields = {"business_place_id"}
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set - nullable_fields
        ):
            raise ValueError("Operating settings cannot be null")
        address_fields = {
            "business_address",
            "business_place_id",
            "business_latitude",
            "business_longitude",
        }
        if self.model_fields_set & address_fields and not {
            "business_address",
            "business_latitude",
            "business_longitude",
        }.issubset(self.model_fields_set):
            raise ValueError(
                "business_address, business_latitude and business_longitude must be updated together"
            )
        return self


class ProviderServiceAreasUpdate(BaseModel):
    service_location_ids: list[int] = Field(min_length=1)

    @field_validator("service_location_ids")
    @classmethod
    def unique_positive_ids(cls, values):
        if any(value <= 0 for value in values):
            raise ValueError("service_location_ids must be positive")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate service locations are not allowed")
        return values
