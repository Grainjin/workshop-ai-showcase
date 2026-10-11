from backend.core.serialize import jsonable


def is_success_response(data):
    return (
        isinstance(data, dict)
        and data.get("success") is True
        and "message" in data
        and "data" in data
    )


def success_response(data=None, message: str = "Success"):
    if is_success_response(data):
        return data

    if isinstance(data, dict) and message == "Success":
        message = data.get("message", message)
        data = data.copy()
        data.pop("message", None)
        data = data or None

    return {
        "success": True,
        "message": message,
        "data": jsonable(data),
    }


def error_response(
    message: str = "Error",
    code: int = 400,
    detail=None,
    errors=None,
):
    return {
        "success": False,
        "message": message,
        "error": {
            "code": code,
            "detail": detail,
            "errors": errors,
        },
    }
