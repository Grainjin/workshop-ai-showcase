from urllib.parse import urlsplit

from fastapi import Request


def payment_result_url_for_request(request: Request) -> str | None:
    """Build a trusted payment-result URL from the browser-supplied Origin.

    Browsers control the Origin header, so the customer cannot inject an
    arbitrary redirect target through the payment payload. Native clients and
    non-browser callers omit Origin and continue to use the configured fallback.
    """

    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        return None

    parsed = urlsplit(origin)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None

    return f"{parsed.scheme}://{parsed.netloc}/payment-result"
