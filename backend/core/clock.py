"""UTC helpers and marketplace timezone conversion utilities."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


WORKSHOP_TIMEZONE = ZoneInfo("Europe/Istanbul")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_workshop_datetime(value: datetime) -> datetime:
    """Interpret a naive value as marketplace local time and convert instants."""
    if value.tzinfo is None:
        return value.replace(tzinfo=WORKSHOP_TIMEZONE)
    return value.astimezone(WORKSHOP_TIMEZONE)


def parse_dt(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def serialize_dt(value: datetime | str | None) -> str | None:
    parsed = parse_dt(value)
    return parsed.isoformat() if parsed is not None else None
