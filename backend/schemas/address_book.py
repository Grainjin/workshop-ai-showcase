from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class CustomerAddressBase(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    place_id: str = Field(min_length=1, max_length=256)
    formatted_address: str = Field(min_length=1, max_length=1024)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    service_location_id: int | None = Field(default=None, gt=0)
    is_default: bool = False

    @field_validator("label", "place_id", "formatted_address")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value


class CustomerAddressCreate(CustomerAddressBase):
    pass


class CustomerAddressUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=64)
    is_default: bool | None = None

    @field_validator("label")
    @classmethod
    def trim_label(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Label cannot be null")
        value = value.strip()
        if not value:
            raise ValueError("Label cannot be empty")
        return value


class CustomerAddressResponse(CustomerAddressBase):
    id: int
    customer_id: int
    created_at: datetime
    updated_at: datetime
