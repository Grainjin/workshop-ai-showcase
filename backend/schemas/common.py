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

DataT = TypeVar("DataT")

class ApiResponse(BaseModel, Generic[DataT]):
    success: bool = True
    message: str = "Success"
    data: DataT | None = None

class ErrorInfo(BaseModel):
    code: int
    detail: Any = None
    errors: Any = None

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error: ErrorInfo

class PaginatedData(BaseModel, Generic[DataT]):
    items: list[DataT]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

