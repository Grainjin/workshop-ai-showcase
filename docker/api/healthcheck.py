"""Probe local API liveness on the platform-assigned port; no database writes."""

import os
import sys
from urllib.error import URLError
from urllib.request import urlopen


if __name__ == "__main__":
    try:
        port = int(os.getenv("PORT", "8000"))
        if not 1 <= port <= 65535:
            raise ValueError("Invalid port")
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=3) as response:
            sys.exit(0 if response.status == 200 else 1)
    except (OSError, URLError, ValueError):
        sys.exit(1)
