"""ChatGPT Plus/Pro device-code login (Codex CLI flow)."""

from __future__ import annotations

import base64
import json
import threading
import time
from pathlib import Path

import httpx

from backend.ai.oauth.files import read_secret_file, write_secret_file
from backend.ai.oauth.http import HttpStatusError, OAuthProtocolError, post_form, post_json

CHATGPT_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CHATGPT_ISSUER = "https://auth.openai.com"
CHATGPT_CODEX_URL = "https://chatgpt.com/backend-api/codex/responses"
CHATGPT_CLIENT_VERSION = "1.0.0"
USER_AGENT = "workshop-ai/0.1.0"
POLL_TIMEOUT_SECONDS = 300
MIN_INTERVAL_SECONDS = 1
SAFETY_WAIT_SECONDS = 3
REFRESH_SKEW_SECONDS = 120


def account_id_from_jwt(token: str) -> str:
    parts = token.split(".")
    if len(parts) < 2:
        return ""
    payload = parts[1]
    padding = "=" * ((4 - len(payload) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload + padding)
        claims = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return ""

    account = claims.get("chatgpt_account_id") or ""
    auth = claims.get("https://api.openai.com/auth") or {}
    if not account and isinstance(auth, dict):
        account = auth.get("chatgpt_account_id") or ""
    orgs = claims.get("organizations") or []
    if not account and orgs and isinstance(orgs, list) and isinstance(orgs[0], dict):
        account = orgs[0].get("id") or ""
    return str(account)


class ChatGPTOAuth:
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

    def account_id(self) -> str:
        with self._lock:
            return str((self._stored or {}).get("account_id") or "")

    def status(self) -> dict:
        with self._lock:
            pending = self._pending
            stored = self._stored
        connected = bool(stored and stored.get("access"))
        out: dict = {"connected": connected, "provider": "chatgpt"}
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
        device = post_json(
            self.http,
            f"{CHATGPT_ISSUER}/api/accounts/deviceauth/usercode",
            {"client_id": CHATGPT_CLIENT_ID},
            {"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        auth_id = device.get("device_auth_id") or ""
        user_code = device.get("user_code") or ""
        if not auth_id or not user_code:
            raise ValueError("ChatGPT returned an incomplete login code")

        interval = _seconds(device.get("interval"), 5)
        self._cancel.set()
        self._cancel = threading.Event()
        pending = {
            "auth_id": auth_id,
            "user_code": user_code,
            "url": f"{CHATGPT_ISSUER}/codex/device",
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
            raise ValueError("Not signed in to ChatGPT")
        expires = int(stored.get("expires") or 0)
        if expires and expires - time.time() > REFRESH_SKEW_SECONDS:
            return stored["access"]
        if not stored.get("refresh"):
            return stored["access"]
        return self._refresh(stored)["access"]

    def _refresh(self, prev: dict) -> dict:
        token = post_form(
            self.http,
            f"{CHATGPT_ISSUER}/oauth/token",
            {
                "grant_type": "refresh_token",
                "refresh_token": prev["refresh"],
                "client_id": CHATGPT_CLIENT_ID,
            },
            {"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        stored = _store_chatgpt(token, prev)
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
                auth = post_json(
                    self.http,
                    f"{CHATGPT_ISSUER}/api/accounts/deviceauth/token",
                    {
                        "device_auth_id": pending["auth_id"],
                        "user_code": pending["user_code"],
                    },
                    {"User-Agent": USER_AGENT, "Accept": "application/json"},
                )
            except (HttpStatusError, OAuthProtocolError) as error:
                if getattr(error, "status", 0) in {403, 404}:
                    if cancel.wait(wait + SAFETY_WAIT_SECONDS):
                        return
                    continue
                self._fail(pending, str(error))
                return
            except Exception as error:
                self._fail(pending, str(error))
                return

            code = auth.get("authorization_code") or ""
            verifier = auth.get("code_verifier") or ""
            if code:
                try:
                    token = self._exchange(code, verifier)
                    stored = _store_chatgpt(token, None)
                    with self._lock:
                        if self._pending is pending:
                            self._stored = stored
                            pending["status"] = "ok"
                            self._pending = None
                    write_secret_file(self.path, stored)
                    from backend.ai.oauth.runtime import set_saved_auth

                    set_saved_auth("chatgpt")
                except Exception as error:
                    self._fail(pending, str(error))
                return

            if cancel.wait(wait + SAFETY_WAIT_SECONDS):
                return
        self._fail(pending, "Login timed out — try again")

    def _exchange(self, code: str, verifier: str) -> dict:
        token = post_form(
            self.http,
            f"{CHATGPT_ISSUER}/oauth/token",
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": f"{CHATGPT_ISSUER}/deviceauth/callback",
                "client_id": CHATGPT_CLIENT_ID,
                "code_verifier": verifier,
            },
            {"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        if not token.get("access_token"):
            raise ValueError("ChatGPT did not return an access token")
        return token

    def _fail(self, pending: dict, message: str) -> None:
        with self._lock:
            if self._pending is not pending:
                return
            pending["status"] = "error"
            pending["error"] = message


def _store_chatgpt(token: dict, prev: dict | None) -> dict:
    refresh = token.get("refresh_token") or (prev or {}).get("refresh") or ""
    expires_in = int(token.get("expires_in") or 0)
    expires = int(time.time() + (expires_in or 3600))
    access = token.get("access_token") or ""
    account = account_id_from_jwt(token.get("id_token") or "") or account_id_from_jwt(
        access
    )
    if not account and prev:
        account = prev.get("account_id") or ""
    return {
        "access": access,
        "refresh": refresh,
        "expires": expires,
        "account_id": account,
        "updated_at": int(time.time()),
    }


def _seconds(value, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback
