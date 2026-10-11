"""xAI SuperGrok / X Premium+ device-code login (RFC 8628)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import httpx

from backend.ai.oauth.files import read_secret_file, write_secret_file
from backend.ai.oauth.http import OAuthProtocolError, post_form

XAI_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
XAI_DEVICE_URL = "https://auth.x.ai/oauth2/device/code"
XAI_TOKEN_URL = "https://auth.x.ai/oauth2/token"
XAI_SCOPE = "openid profile email offline_access grok-cli:access api:access"
XAI_API_BASE = "https://api.x.ai/v1"
DEFAULT_GROK_MODEL = "grok-4.7"
USER_AGENT = "workshop-ai/0.1.0"
POLL_TIMEOUT_SECONDS = 300
MIN_INTERVAL_SECONDS = 1
REFRESH_SKEW_SECONDS = 120


class GrokOAuth:
    def __init__(self, path: Path):
        self.path = path
        self.http = httpx.Client(timeout=30.0)
        self._lock = threading.Lock()
        self._stored = read_secret_file(path)
        self._pending: dict | None = None
        self._cancel = threading.Event()

    def connected(self) -> bool:
        with self._lock:
            return bool(self._stored and self._stored.get("access"))

    def status(self) -> dict:
        with self._lock:
            pending = self._pending
            stored = self._stored
        connected = bool(stored and stored.get("access"))
        out: dict = {"connected": connected, "provider": "grok"}
        if pending:
            out.update(
                {
                    "pending": True,
                    "status": pending.get("status") or "pending",
                    "user_code": pending.get("user_code") or "",
                    "url": pending.get("url") or "",
                    "error": pending.get("error") or "",
                }
            )
        else:
            out.update(
                {
                    "pending": False,
                    "status": "ok" if connected else "idle",
                    "user_code": "",
                    "url": "",
                    "error": "",
                }
            )
        return out

    def start(self) -> dict:
        device = post_form(
            self.http,
            XAI_DEVICE_URL,
            {
                "client_id": XAI_CLIENT_ID,
                "scope": XAI_SCOPE,
            },
            {"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        device_code = str(device.get("device_code") or "")
        user_code = str(device.get("user_code") or "")
        url = str(
            device.get("verification_uri_complete")
            or device.get("verification_uri")
            or ""
        )
        if not device_code or not user_code or not url:
            raise ValueError("Grok returned an incomplete login code")

        interval = _seconds(device.get("interval"), 5)
        self._cancel.set()
        self._cancel = threading.Event()
        pending = {
            "device_code": device_code,
            "user_code": user_code,
            "url": url,
            "status": "pending",
            "error": "",
        }
        with self._lock:
            self._pending = pending
        thread = threading.Thread(
            target=self._poll,
            args=(pending, interval, self._cancel),
            daemon=True,
        )
        thread.start()
        return self.status()

    def cancel(self) -> dict:
        self._cancel.set()
        with self._lock:
            self._pending = None
        return self.status()

    def logout(self) -> dict:
        self.cancel()
        with self._lock:
            self._stored = None
        if self.path.exists():
            self.path.unlink()
        return self.status()

    def bearer(self) -> str:
        with self._lock:
            stored = dict(self._stored or {})
        if not stored.get("access"):
            raise ValueError("Not signed in to Grok")
        expires = int(stored.get("expires") or 0)
        if expires and expires - time.time() > REFRESH_SKEW_SECONDS:
            return stored["access"]
        if not stored.get("refresh"):
            return stored["access"]
        return self._refresh(stored)["access"]

    def _refresh(self, prev: dict) -> dict:
        token = post_form(
            self.http,
            XAI_TOKEN_URL,
            {
                "grant_type": "refresh_token",
                "refresh_token": prev["refresh"],
                "client_id": XAI_CLIENT_ID,
            },
            {"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        stored = _store_grok(token, prev)
        with self._lock:
            self._stored = stored
        write_secret_file(self.path, stored)
        return stored

    def _poll(self, pending: dict, interval: float, cancel: threading.Event) -> None:
        deadline = time.time() + POLL_TIMEOUT_SECONDS
        wait = max(interval, MIN_INTERVAL_SECONDS)
        while time.time() < deadline:
            if cancel.wait(0):
                return
            try:
                token = post_form(
                    self.http,
                    XAI_TOKEN_URL,
                    {
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "client_id": XAI_CLIENT_ID,
                        "device_code": pending["device_code"],
                    },
                    {"User-Agent": USER_AGENT, "Accept": "application/json"},
                )
            except OAuthProtocolError as error:
                if error.code in {"authorization_pending", "slow_down"}:
                    if error.code == "slow_down":
                        wait += 2
                    if cancel.wait(wait):
                        return
                    continue
                self._fail(pending, str(error))
                return
            except Exception as error:
                self._fail(pending, str(error))
                return

            if token.get("access_token"):
                stored = _store_grok(token, None)
                with self._lock:
                    if self._pending is pending:
                        self._stored = stored
                        pending["status"] = "ok"
                        self._pending = None
                write_secret_file(self.path, stored)
                from backend.ai.oauth.runtime import set_saved_auth

                set_saved_auth("grok")
                return
            if cancel.wait(wait):
                return
        self._fail(pending, "Login timed out — try again")

    def _fail(self, pending: dict, message: str) -> None:
        with self._lock:
            if self._pending is not pending:
                return
            pending["status"] = "error"
            pending["error"] = message


def _store_grok(token: dict, prev: dict | None) -> dict:
    refresh = token.get("refresh_token") or (prev or {}).get("refresh") or ""
    expires_in = int(token.get("expires_in") or 0)
    return {
        "access": token.get("access_token") or "",
        "refresh": refresh,
        "expires": int(time.time() + (expires_in or 3600)),
        "updated_at": int(time.time()),
    }


def _seconds(value, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback
