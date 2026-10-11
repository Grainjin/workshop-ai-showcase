import type { BookingDetail, ReferencePriceRange } from "../types/booking";

export type ReferencePriceAudience = "provider" | "customer";

const wholeNumberFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

export function buildReferencePricePresentation(
  range: ReferencePriceRange | null | undefined,
  audience: ReferencePriceAudience,
) {
  const label =
    audience === "provider"
      ? "Recommended price range"
      : "Typical range for similar jobs";

  if (
    range?.has_history &&
    range.minimum != null &&
    range.maximum != null
  ) {
    return {
      label,
      value: `₺${wholeNumberFormatter.format(range.minimum)}–₺${wholeNumberFormatter.format(range.maximum)}`,
    };
  }

  return {
    label,
    value:
      audience === "customer" ? "No historical data for similar jobs" : null,
  };
}

export function shouldShowCustomerReferencePrice(
  booking: Pick<
    BookingDetail,
    | "status"
    | "quote_amount"
    | "expected_service_amount"
    | "visit_fee_amount"
    | "final_quote_amount"
    | "last_declined_quote"
    | "last_declined_final_quote"
  >,
) {
  return Boolean(
    booking.quote_amount != null ||
      booking.expected_service_amount != null ||
      booking.visit_fee_amount != null ||
      booking.final_quote_amount != null ||
      booking.last_declined_quote != null ||
      booking.last_declined_final_quote != null,
  );
}

export async function resolveBookingReferenceDetail<T extends { id: number }>(
  booking: T,
  loadDetail: (bookingId: number) => Promise<T | null | undefined>,
) {
  try {
    return (await loadDetail(booking.id)) ?? booking;
  } catch {
    return booking;
  }
}
