from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.utils.response import error_response


async def http_exception_handler(request: Request, exc: HTTPException):
    message = exc.detail

    if not isinstance(message, str):
        message = "Request failed"

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            message=message,
            code=exc.status_code,
            detail=exc.detail,
        ),
        headers=exc.headers,
    )


def format_validation_error(error: dict):
    location = error.get("loc", [])
    field_parts = [
        str(part) for part in location if part not in ["body", "query", "path"]
    ]

    return {
        "field": ".".join(field_parts) if field_parts else None,
        "message": error.get("msg", "Invalid value"),
        "type": error.get("type"),
    }


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    errors = [format_validation_error(error) for error in exc.errors()]

    return JSONResponse(
        status_code=422,
        content=error_response(
            message="Validation error",
            code=422,
            errors=errors,
        ),
    )


async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=error_response(
            message="Internal server error",
            code=500,
            detail=str(exc),
        ),
    )
