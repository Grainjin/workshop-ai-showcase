from typing import Literal

from pydantic import BaseModel, Field


ServiceLocationLevel = Literal["province", "city", "district"]


class ServiceLocationResponse(BaseModel):
    id: int
    parent_id: int | None = None
    code: str
    name: str
    level: ServiceLocationLevel


class ServiceLocationListResponse(BaseModel):
    items: list[ServiceLocationResponse] = Field(default_factory=list)
