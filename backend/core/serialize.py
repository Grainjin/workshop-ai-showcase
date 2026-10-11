from datetime import date, datetime
from decimal import Decimal

from backend.core.clock import serialize_dt


def serialize_money(value) -> float | None:
    if value is None:
        return None
    return float(value)


def jsonable(value):
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, datetime):
        return serialize_dt(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
