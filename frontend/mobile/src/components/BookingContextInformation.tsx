import { StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme/theme";
import type { BookingDetail } from "../types/booking";

export function BookingContextInformation({
  booking,
}: {
  booking: BookingDetail;
}) {
  const initialDeclineReason = booking.status === "pending"
    ? booking.last_declined_quote?.decline_reason
    : null;
  const finalDeclineReason =
    booking.status === "awaiting_final_quote"
      ? booking.final_quote_decline_reason
      : null;
  const currentContext = initialDeclineReason
    ? {
        label: "Customer decline reason",
        value: initialDeclineReason,
      }
    : finalDeclineReason
      ? {
          label: "Customer final quote decline reason",
          value: finalDeclineReason,
        }
      : booking.status === "quoted" && booking.quote_message?.trim()
        ? {
            label: "Quote message",
            value: booking.quote_message.trim(),
          }
        : booking.status === "final_quote_sent" && booking.final_quote_message?.trim()
          ? {
              label: "Final quote message",
              value: booking.final_quote_message.trim(),
            }
          : !booking.current_refund_request && booking.status_note?.trim()
            ? {
                label: "Latest update",
                value: booking.status_note.trim(),
              }
            : null;

  if (!currentContext) {
    return null;
  }

  return (
    <View style={styles.container}>
      <ContextRow label={currentContext.label} value={currentContext.value} />
    </View>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  row: {
    gap: spacing.xs,
  },
  label: {
    color: colors.mutedText,
    fontSize: 13,
    fontWeight: "700",
  },
  value: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 20,
  },
});
