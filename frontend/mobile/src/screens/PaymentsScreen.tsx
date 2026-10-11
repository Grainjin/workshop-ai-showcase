import { useFocusEffect } from "@react-navigation/native";
import { useCallback, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";

import { getCustomerPayments } from "../api/customer";
import { getProviderPayments } from "../api/provider";
import { MarketplaceBreakdownCard } from "../components/MarketplaceBreakdownCard";
import { SecondaryButton } from "../components/SecondaryButton";
import { useAuth } from "../context/AuthContext";
import { colors, radius, spacing } from "../theme/theme";
import type { PaymentHistoryEntry } from "../types/booking";
import {
  getBookingStatusLabel,
  getPaymentStatusLabel,
} from "../constants/labels";
import { formatDateTime } from "../utils/datetime";
import { getErrorMessage } from "../utils/errors";
import { formatMoney } from "../utils/money";
import { getPaymentStatusTone } from "../utils/payment";

/**
 * History only: what was charged, for which booking, and when.
 *
 * There is deliberately no stored-card list. The demo has no payment-method
 * vault, so offering to "manage cards" would be a control that cannot work.
 */
export function PaymentsScreen() {
  const { user } = useAuth();
  const [payments, setPayments] = useState<PaymentHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");

  const isProvider = user?.role === "provider";

  const loadPayments = useCallback(async () => {
    if (!user || user.role === "admin") {
      setPayments([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setMessage("");
    try {
      const result = isProvider
        ? await getProviderPayments(1, 100)
        : await getCustomerPayments(1, 100);

      setPayments(result?.items ?? []);
    } catch (error) {
      setPayments([]);
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [isProvider, user]);

  useFocusEffect(
    useCallback(() => {
      void loadPayments();
    }, [loadPayments]),
  );

  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Payments</Text>
        <SecondaryButton
          disabled={isLoading}
          label="Refresh"
          onPress={() => void loadPayments()}
        />
      </View>

      <Text style={styles.subtitle}>
        {isProvider
          ? "Payments customers have made for your bookings."
          : "What you have paid, and for which booking."}
      </Text>

      {message ? <Text style={styles.message}>{message}</Text> : null}

      {isLoading ? (
        <ActivityIndicator accessibilityLabel="Loading payments" color={colors.primary} />
      ) : payments.length > 0 ? (
        payments.map((payment) => (
          <PaymentRow key={payment.id} isProvider={isProvider} payment={payment} />
        ))
      ) : !message ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyTitle}>No payments yet</Text>
          <Text style={styles.emptyBody}>
            {isProvider
              ? "Payments appear here once a customer pays for a booking."
              : "Once you pay for a booking it shows up here."}
          </Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

function PaymentRow({
  isProvider,
  payment,
}: {
  isProvider: boolean;
  payment: PaymentHistoryEntry;
}) {
  const counterparty = isProvider
    ? payment.booking?.customer?.name
    : payment.booking?.provider?.business_name;

  return (
    <View style={styles.card}>
      <View style={styles.cardTop}>
        <Text style={styles.amount}>{formatMoney(payment.amount)}</Text>
        <StatusPill status={payment.status} />
      </View>

      <Text style={styles.cardLine} numberOfLines={2}>
        {payment.booking?.service_description ?? `Booking #${payment.booking_id}`}
        {counterparty ? ` · ${counterparty}` : ""}
      </Text>

      <View style={styles.stateRow}>
        <Text style={styles.stateLabel}>Payment</Text>
        <Text style={styles.stateValue}>{getPaymentStatusLabel(payment.status)}</Text>
      </View>
      {payment.booking?.status ? (
        <View style={styles.stateRow}>
          <Text style={styles.stateLabel}>Booking</Text>
          <Text style={styles.stateValue}>
            {getBookingStatusLabel(payment.booking.status)}
          </Text>
        </View>
      ) : null}

      <Text style={styles.cardMeta}>
        {payment.paid_at
          ? `Paid ${formatDateTime(payment.paid_at)}`
          : `Created ${formatDateTime(payment.created_at)}`}
        {payment.refunded_at
          ? ` · Refunded ${formatDateTime(payment.refunded_at)}`
          : ""}
      </Text>
      {isProvider ? (
        <MarketplaceBreakdownCard payment={payment} />
      ) : null}
    </View>
  );
}

function StatusPill({ status }: { status: string }) {
  const paymentTone = getPaymentStatusTone(status);
  const tone =
    paymentTone === "success"
      ? styles.pillPaid
      : paymentTone === "muted"
        ? styles.pillRefunded
        : paymentTone === "danger"
          ? styles.pillFailed
          : styles.pillPending;

  return (
    <View style={[styles.pill, tone]}>
      <Text style={styles.pillText}>{getPaymentStatusLabel(status)}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.background,
  },
  content: {
    gap: spacing.md,
    padding: spacing.lg,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "700",
  },
  subtitle: {
    color: colors.mutedText,
    fontSize: 14,
  },
  message: {
    color: colors.danger,
    fontSize: 14,
  },
  card: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  cardTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  amount: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "800",
  },
  cardLine: {
    color: colors.text,
    fontSize: 15,
  },
  stateRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  stateLabel: {
    color: colors.mutedText,
    fontSize: 13,
  },
  stateValue: {
    color: colors.text,
    flexShrink: 1,
    fontSize: 13,
    fontWeight: "700",
    textAlign: "right",
  },
  cardMeta: {
    color: colors.mutedText,
    fontSize: 13,
  },
  pill: {
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  pillPaid: {
    backgroundColor: "#E7F6F0",
  },
  pillRefunded: {
    backgroundColor: "#FDEEEE",
  },
  pillPending: {
    backgroundColor: colors.border,
  },
  pillFailed: {
    backgroundColor: "#FDEEEE",
  },
  pillText: {
    color: colors.text,
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.5,
  },
  emptyCard: {
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.lg,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
  },
  emptyBody: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 21,
  },
});
