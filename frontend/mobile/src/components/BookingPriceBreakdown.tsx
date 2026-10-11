import { StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme/theme";
import type { BookingDetail } from "../types/booking";
import { formatMoney } from "../utils/money";
import { getDemoPaymentDisclosure } from "../utils/payment";

type QuoteSnapshot = {
  visit_fee_amount?: number | null;
  expected_service_amount?: number | null;
  total_amount?: number | null;
  quote_message?: string | null;
  decline_reason?: string | null;
};

const POST_FINAL_QUOTE_STATUSES = new Set([
  "awaiting_service_payment",
  "service_paid",
  "awaiting_confirmation",
  "completed",
  "refunded",
  "partially_refunded",
  "visit_completed_closed",
  "service_cancelled_after_payment",
]);

export function BookingPriceBreakdown({
  booking,
  showInitialQuote = true,
  showFinalQuote = true,
  showPreviousDeclined = true,
  showPreviousFinalQuote = true,
}: {
  booking: BookingDetail;
  showInitialQuote?: boolean;
  showFinalQuote?: boolean;
  showPreviousDeclined?: boolean;
  showPreviousFinalQuote?: boolean;
}) {
  const hasInitialQuote =
    booking.visit_fee_amount != null || booking.expected_service_amount != null;
  const visitFee = booking.visit_fee_amount ?? booking.quote_amount;
  const expectedService = booking.expected_service_amount ?? booking.quote_amount;
  const hasCurrentInitialQuote = hasInitialQuote || booking.quote_amount != null;
  const hasCurrentFinalQuote = showFinalQuote && booking.final_quote_amount != null;
  const previousQuote = booking.last_declined_quote;
  const previousFinalQuote = booking.last_declined_final_quote;
  const hasAcceptedFinalQuote =
    booking.final_quote_amount != null &&
    (booking.final_quote_confirmed_at != null ||
      POST_FINAL_QUOTE_STATUSES.has(String(booking.status)));
  const hasPreviousQuote =
    showPreviousDeclined && previousQuote != null && !hasAcceptedFinalQuote;
  const hasPreviousFinalQuote =
    showPreviousFinalQuote &&
    previousFinalQuote != null &&
    !hasAcceptedFinalQuote;
  const hasVisibleCurrentInitialQuote =
    showInitialQuote && hasCurrentInitialQuote && !hasAcceptedFinalQuote;
  const title = hasVisibleCurrentInitialQuote || hasCurrentFinalQuote
    ? "Price details"
    : "Quote history";
  const showFinalVisitFee =
    !hasVisibleCurrentInitialQuote && (hasCurrentFinalQuote || hasPreviousFinalQuote);

  if (
    !hasCurrentInitialQuote &&
    !hasCurrentFinalQuote &&
    !hasPreviousQuote &&
    !hasPreviousFinalQuote
  ) {
    return null;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      {getDemoPaymentDisclosure(booking.payment_method) ? (
        <Text style={styles.label}>{getDemoPaymentDisclosure(booking.payment_method)}</Text>
      ) : null}
      {hasVisibleCurrentInitialQuote ? (
        <>
          <PriceRow label="Visit fee" value={visitFee == null ? "—" : formatMoney(visitFee)} />
          <PriceRow
            label="Expected service amount"
            value={expectedService == null ? "—" : formatMoney(expectedService)}
          />
          <PriceRow
            label="Expected total"
            value={hasInitialQuote ? formatMoney(booking.total_amount) : "—"}
            emphasized
          />
        </>
      ) : null}
      {hasCurrentFinalQuote ? (
        <>
          {showFinalVisitFee ? (
            <PriceRow
              label="Visit fee"
              value={formatMoney(booking.visit_fee_amount)}
            />
          ) : null}
          <PriceRow label="Service amount" value={formatMoney(booking.final_quote_amount)} emphasized />
        </>
      ) : null}
      {hasPreviousQuote ? (
        <>
          <PriceRow
            label={hasCurrentInitialQuote ? "Previous visit fee" : "Visit fee"}
            value={formatMoney(previousQuote?.visit_fee_amount ?? previousQuote?.quote_amount)}
          />
          <PriceRow
            label={hasCurrentInitialQuote ? "Previous Expected service amount" : "Expected service amount"}
            value={formatMoney(previousQuote?.expected_service_amount ?? previousQuote?.quote_amount)}
          />
          <PriceRow
            emphasized
            label={hasCurrentInitialQuote ? "Previous total" : "Expected total"}
            value={formatMoney(
              previousQuote?.total_amount ??
                (previousQuote?.visit_fee_amount ?? previousQuote?.quote_amount ?? 0) +
                  (previousQuote?.expected_service_amount ?? previousQuote?.quote_amount ?? 0),
            )}
          />
        </>
      ) : null}
      {hasPreviousFinalQuote ? (
        <>
          {!hasCurrentFinalQuote ? (
            <PriceRow
              label="Visit fee"
              value={formatMoney(
                previousFinalQuote?.visit_fee_amount ?? booking.visit_fee_amount,
              )}
            />
          ) : null}
          <PriceRow
            emphasized
            label="Previous service amount"
            value={formatMoney(previousFinalQuote.quote_amount)}
          />
          {!hasCurrentFinalQuote ? (
            <PriceRow label="Status" value="Waiting for revised quote" />
          ) : null}
        </>
      ) : null}
    </View>
  );
}

function PriceRow({
  emphasized = false,
  label,
  value,
}: {
  emphasized?: boolean;
  label: string;
  value: string;
}) {
  return (
    <View style={styles.row}>
      <Text style={[styles.label, emphasized ? styles.emphasized : null]}>{label}</Text>
      <Text style={[styles.value, emphasized ? styles.emphasized : null]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.xs,
    marginTop: spacing.sm,
  },
  title: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "800",
    marginBottom: spacing.xs,
  },
  row: {
    alignItems: "flex-start",
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  label: {
    color: colors.mutedText,
    flex: 1,
    fontSize: 13,
  },
  value: {
    color: colors.text,
    flex: 1,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "right",
  },
  emphasized: {
    fontWeight: "800",
  },
  separator: {
    borderTopColor: colors.border,
    borderTopWidth: StyleSheet.hairlineWidth,
    marginTop: spacing.sm,
  },
});
