from typing import Any

from fastapi import APIRouter
from fastapi.datastructures import DefaultPlaceholder

from backend.schemas import ApiResponse, ErrorResponse

DEFAULT_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Bad Request"},
    401: {"model": ErrorResponse, "description": "Unauthorized"},
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Not Found"},
    422: {"model": ErrorResponse, "description": "Validation Error"},
    500: {"model": ErrorResponse, "description": "Internal Server Error"},
}


class ApiRouter(APIRouter):
    def add_api_route(self, path: str, endpoint, *args, **kwargs):
        response_model = kwargs.get("response_model")
        if response_model is None or isinstance(response_model, DefaultPlaceholder):
            kwargs["response_model"] = ApiResponse[Any]

        responses = kwargs.get("responses") or {}
        kwargs["responses"] = {**DEFAULT_ERROR_RESPONSES, **responses}
        return super().add_api_route(path, endpoint, *args, **kwargs)
