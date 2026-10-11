from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from backend import models


def _no_history() -> dict[str, bool | int | str | None]:
    return {
        "has_history": False,
        "minimum": None,
        "maximum": None,
        "currency": "TRY",
        "sample_count": 0,
    }


def calculate_reference_price_range(
    booking: models.Booking,
    db: Session,
) -> dict[str, bool | int | str | None]:
    if booking.service_category is None:
        return _no_history()

    revisions = (
        db.query(models.BookingQuoteRevision)
        .join(models.Booking, models.Booking.id == models.BookingQuoteRevision.booking_id)
        .filter(
            models.Booking.service_category == booking.service_category,
            models.Booking.id != booking.id,
        )
        .order_by(
            models.BookingQuoteRevision.booking_id.asc(),
            models.BookingQuoteRevision.revision_number.desc(),
            models.BookingQuoteRevision.created_at.desc(),
            models.BookingQuoteRevision.id.desc(),
        )
        .all()
    )

    latest_amounts: list[Decimal] = []
    seen_booking_ids: set[int] = set()
    for revision in revisions:
        if revision.booking_id in seen_booking_ids:
            continue
        seen_booking_ids.add(revision.booking_id)
        latest_amounts.append(Decimal(revision.quote_amount))

    if not latest_amounts:
        return _no_history()

    average = sum(latest_amounts, Decimal("0")) / len(latest_amounts)
    minimum = (average * Decimal("0.9")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    maximum = (average * Decimal("1.1")).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return {
        "has_history": True,
        "minimum": int(minimum),
        "maximum": int(maximum),
        "currency": "TRY",
        "sample_count": len(latest_amounts),
    }
