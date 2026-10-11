import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, spacing } from "../theme/theme";
import type { BookingDetail } from "../types/booking";
import { formatDateTime } from "../utils/datetime";

export function BookingCoreDetails({
  booking,
  onOpenProvider,
  role,
  includeLifecycleDates = false,
}: {
  booking: BookingDetail;
  onOpenProvider?: (booking: BookingDetail) => void;
  role: "customer" | "provider";
  includeLifecycleDates?: boolean;
}) {
  const participantLabel = role === "customer" ? "Provider" : "Customer";
  const participantValue =
    role === "customer"
      ? booking.provider?.business_name || `Provider #${booking.provider_profile_id}`
      : booking.customer?.name || `Customer #${booking.customer_id}`;

  return (
    <View style={styles.container}>
      <Row label={participantLabel}>
        {role === "customer" && onOpenProvider ? (
          <Pressable
            accessibilityHint="Opens the provider profile"
            accessibilityLabel={`Open ${participantValue}`}
            accessibilityRole="link"
            onPress={() => onOpenProvider(booking)}
          >
            <Text style={[styles.value, styles.link]}>{participantValue}</Text>
          </Pressable>
        ) : (
          <Text style={styles.value}>{participantValue}</Text>
        )}
      </Row>
      <Row label="Booking title" value={booking.title} />
      <Row label="Service description" value={booking.service_description} />
      <Row label="Service address" value={booking.service_address} />
      <Row
        label="Scheduled time"
        value={`${formatDateTime(booking.scheduled_start_time)} - ${formatDateTime(
          booking.scheduled_end_time,
        )}`}
      />
      {includeLifecycleDates ? (
        <>
          <Row label="Booked at" value={formatDateTime(booking.booking_at)} />
          <Row
            label="Completed at"
            value={booking.completed_at ? formatDateTime(booking.completed_at) : "—"}
          />
        </>
      ) : null}
    </View>
  );
}

function Row({
  children,
  label,
  value,
}: {
  children?: React.ReactNode;
  label: string;
  value?: string;
}) {
  return (
    <View style={styles.row}>
      <Text style={styles.label}>{label}</Text>
      {children || <Text style={styles.value}>{value || "—"}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
  },
  row: {
    gap: spacing.xs,
  },
  label: {
    color: colors.mutedText,
    fontSize: 13,
    fontWeight: "600",
  },
  value: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  link: {
    color: colors.primary,
    fontWeight: "700",
    textDecorationLine: "underline",
  },
});
