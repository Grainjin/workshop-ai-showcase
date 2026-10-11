"""Validate public Demo deployment inputs without importing application services."""

import os
from pathlib import Path
import sys
from urllib.parse import urlsplit


def validate(role: str) -> None:
    if os.getenv("DEMO_MODE") != "true":
        raise ValueError("Public deployment requires DEMO_MODE=true")
    if os.getenv("WORKSHOP_PAYMENT_MODE") != "demo":
        raise ValueError("Public deployment requires WORKSHOP_PAYMENT_MODE=demo")
    origins = os.getenv("WORKSHOP_CORS_ORIGINS", "").split(",")
    for origin in origins:
        try:
            url = urlsplit(origin.strip())
            valid = (url.scheme == "https" and bool(url.hostname) and not url.username
                     and not url.password and url.path == ""
                     and not url.query and not url.fragment)
            _ = url.port  # Reject malformed ports before serving traffic.
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Public deployment requires explicit HTTPS CORS origins")
    if role in ("api", "worker"):
        for part in ("PRIVATE", "PUBLIC"):
            name = f"WORKSHOP_JWT_{part}_KEY"
            path = Path(os.getenv(f"{name}_PATH", f"backend/certs/jwt-{part.lower()}.pem"))
            if not os.getenv(name, "").strip() and not (path.is_file() and path.stat().st_size):
                raise ValueError("Public deployment requires provisioned, persistent JWT keys")


if __name__ == "__main__":
    try:
        validate(sys.argv[1])
    except (ValueError, OSError):
        # Only fixed diagnostic messages; URLs, key material and filesystem paths
        # must never appear in process logs.
        sys.exit("Public deployment configuration invalid: check demo/payment flags, "
                 "HTTPS CORS origins and persistent JWT keys.")
