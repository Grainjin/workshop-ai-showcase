"""Google Places API (New) proxy service."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from backend.config import GOOGLE_MAPS_API_KEY

AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_REQUESTS_PER_WINDOW = 60
RATE_LIMIT_WINDOW_SECONDS = 60.0


class _RequestRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, client_id: str) -> bool:
        now = monotonic()
        with self._lock:
            requests = self._requests[client_id]
            while requests and now - requests[0] >= self.window_seconds:
                requests.popleft()

            if len(requests) >= self.max_requests:
                return False

            requests.append(now)
            return True


_rate_limiter = _RequestRateLimiter(
    max_requests=MAX_REQUESTS_PER_WINDOW,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)


def require_places_api_key() -> str:
    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Places service is not configured",
        )

    return GOOGLE_MAPS_API_KEY


def enforce_rate_limit(client_id: str) -> None:
    if not _rate_limiter.allow(client_id):
        raise HTTPException(
            status_code=429,
            detail="Too many Places requests",
            headers={"Retry-After": str(int(RATE_LIMIT_WINDOW_SECONDS))},
        )


def _request_google_json(
    method: str,
    url: str,
    *,
    api_key: str,
    field_mask: str,
    json_body: dict | None = None,
) -> dict:
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = client.request(
                method,
                url,
                headers=headers,
                json=json_body,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Places service timed out",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="Places service is unavailable",
        ) from exc

    if response.is_error:
        if response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail="Places service rate limit exceeded",
                headers={"Retry-After": "60"},
            )
        if 400 <= response.status_code < 500:
            status_code = 404 if response.status_code == 404 else 400
            raise HTTPException(
                status_code=status_code,
                detail="Invalid Places request",
            )
        raise HTTPException(
            status_code=502,
            detail="Places service returned an upstream error",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Places service returned an invalid response",
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502,
            detail="Places service returned an invalid response",
        )

    return payload


def autocomplete(query: str) -> dict:
    api_key = require_places_api_key()
    payload = _request_google_json(
        "POST",
        AUTOCOMPLETE_URL,
        api_key=api_key,
        field_mask=(
            "suggestions.placePrediction.placeId,"
            "suggestions.placePrediction.text.text"
        ),
        json_body={"input": query},
    )

    suggestions = []
    for suggestion in payload.get("suggestions", []):
        if not isinstance(suggestion, dict):
            continue

        prediction = suggestion.get("placePrediction")
        if not isinstance(prediction, dict):
            continue

        place_id = prediction.get("placeId")
        text = prediction.get("text")
        description = text.get("text") if isinstance(text, dict) else None
        if (
            isinstance(place_id, str)
            and place_id
            and isinstance(description, str)
            and description
        ):
            suggestions.append(
                {
                    "place_id": place_id,
                    "description": description,
                }
            )

    return {"suggestions": suggestions[:5]}


def get_details(place_id: str) -> dict:
    api_key = require_places_api_key()
    safe_place_id = quote(place_id, safe="")
    payload = _request_google_json(
        "GET",
        PLACE_DETAILS_URL.format(place_id=safe_place_id),
        api_key=api_key,
        field_mask="id,formattedAddress,location",
    )

    location = payload.get("location")
    returned_place_id = payload.get("id")
    formatted_address = payload.get("formattedAddress")
    latitude = location.get("latitude") if isinstance(location, dict) else None
    longitude = location.get("longitude") if isinstance(location, dict) else None

    if (
        not isinstance(returned_place_id, str)
        or not returned_place_id
        or not isinstance(formatted_address, str)
        or not formatted_address
        or not isinstance(latitude, (int, float))
        or isinstance(latitude, bool)
        or not isinstance(longitude, (int, float))
        or isinstance(longitude, bool)
    ):
        raise HTTPException(
            status_code=502,
            detail="Places service returned incomplete place details",
        )

    return {
        "place_id": returned_place_id,
        "formatted_address": formatted_address,
        "latitude": latitude,
        "longitude": longitude,
    }
