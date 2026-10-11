from __future__ import annotations

import json
import os
from pathlib import Path


def write_secret_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, indent=2)
    path.write_text(raw, encoding="utf-8")
    os.chmod(path, 0o600)


def read_secret_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
