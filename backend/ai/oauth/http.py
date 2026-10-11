from __future__ import annotations

import json

import httpx


class HttpStatusError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class OAuthProtocolError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def raise_for_oauth_body(status: int, body: bytes) -> None:
    text = body.decode("utf-8", errors="replace")
    parsed = {}
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {}

    if status < 400:
        return

    error = str(parsed.get("error") or "").strip()
    description = str(parsed.get("error_description") or "").strip()
    message = " ".join(part for part in (error, description) if part)
    if not message:
        message = f"HTTP {status}: {text[:200]}"
    if error:
        raise OAuthProtocolError(error, message, status)
    raise HttpStatusError(status, message)


def post_json(client: httpx.Client, url: str, payload: dict, headers: dict | None = None):
    response = client.post(url, json=payload, headers=headers)
    raise_for_oauth_body(response.status_code, response.content)
    return response.json() if response.content else {}


def post_form(client: httpx.Client, url: str, form: dict, headers: dict | None = None):
    response = client.post(url, data=form, headers=headers)
    raise_for_oauth_body(response.status_code, response.content)
    return response.json() if response.content else {}


def get_json(client: httpx.Client, url: str, headers: dict | None = None):
    response = client.get(url, headers=headers)
    raise_for_oauth_body(response.status_code, response.content)
    return response.json() if response.content else {}
