import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";

import { getCustomerBookings, getCustomerPayments } from "../api/customer";
import { PrimaryButton } from "../components/PrimaryButton";
import { SecondaryButton } from "../components/SecondaryButton";
import { getBookingStatusLabel, getPaymentStatusLabel } from "../constants/labels";
import { colors, radius, spacing } from "../theme/theme";
import type { RootStackParamList } from "../navigation/types";
import type { BookingDetail, PaymentSummary } from "../types/booking";
import { getErrorMessage } from "../utils/errors";
import { formatMoney } from "../utils/money";
import { getDemoPaymentDisclosure } from "../utils/payment";
import {
  savePendingPaymentResult,
} from "../utils/pendingPaymentResult";
import { useAuth } from "../context/AuthContext";

type PaymentResultScreenProps = NativeStackScreenProps<
  RootStackParamList,
  "PaymentResult"
>;

export function PaymentResultScreen({
  navigation,
  route,
}: PaymentResultScreenProps) {
  const { user } = useAuth();
  const bookingId = Number(route.params?.booking_id);
  const [booking, setBooking] = useState<BookingDetail | null>(null);
  const [payment, setPayment] = useState<PaymentSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");

  const loadResult = useCallback(async () => {
    if (!Number.isInteger(bookingId) || bookingId <= 0) {
      setMessage("The payment result is missing its booking reference.");
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setMessage("");
    try {
      const [bookingPage, paymentPage] = await Promise.all([
        getCustomerBookings(undefined, 1, 100),
        getCustomerPayments(1, 100),
      ]);
      const nextBooking =
        bookingPage?.items?.find((item) => item.id === bookingId) ?? null;
      const nextPayment =
        paymentPage?.items
          ?.filter((item) => item.booking_id === bookingId)
          .sort((left, right) =>
            right.created_at.localeCompare(left.created_at),
          )[0] ?? null;

      setBooking(nextBooking);
      setPayment(nextPayment);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [bookingId]);

  useEffect(() => {
    if (!user) {
      void savePendingPaymentResult(route.params);
      setIsLoading(false);
      return;
    }

    void loadResult();
  }, [loadResult, route.params, user]);

  const isPaid = payment?.status === "paid";
  const isAuthorized = payment?.status === "authorized";
  const isRefunded =
    payment?.status === "refunded" || payment?.status === "partially_refunded";
  const isFailed =
    payment?.status === "failed" || payment?.status === "capture_failed";
  const isVoided = payment?.status === "voided";

  if (!user) {
    return (
      <ScrollView contentContainerStyle={styles.content} style={styles.container}>
        <View style={styles.card}>
          <Text style={styles.eyebrow}>Payment result</Text>
          <Text style={styles.title}>Payment callback received</Text>
          <Text style={styles.body}>
            Sign in to view the latest booking and payment status. Your payment
            result reference will be kept and reopened after sign-in.
          </Text>
          <View style={styles.actions}>
            <PrimaryButton
              label="Sign in"
              onPress={() => navigation.navigate("Auth")}
            />
          </View>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.eyebrow}>Payment result</Text>
        <Text style={styles.title}>
          {isLoading
            ? "Checking payment"
            : isPaid
              ? "Payment successful"
              : isAuthorized
                ? "Payment authorized"
                : isRefunded
                  ? "Payment refunded"
                  : isVoided
                    ? "Authorization released"
                    : isFailed
                      ? "Payment failed"
              : "Payment not completed"}
        </Text>

        {isLoading ? (
          <ActivityIndicator color={colors.primary} />
        ) : message ? (
          <Text style={styles.errorText}>{message}</Text>
        ) : (
          <>
            <Text style={styles.body}>
              {getDemoPaymentDisclosure(payment?.payment_method) ?? (isPaid
                ? "Your payment was received. Check the booking status for the next step."
                : isAuthorized
                  ? "Your payment method was authorized. The final charge will be captured after service completion."
                  : isRefunded
                    ? payment?.status === "partially_refunded"
                      ? "Part of this payment was refunded."
                      : "This payment was refunded."
                    : isVoided
                      ? "The payment authorization was released and no charge was captured."
                      : isFailed
                        ? "The payment was not completed. You can try checkout again from the booking page."
                        : "The booking is still awaiting payment. You can try checkout again from the booking page.")}
            </Text>
            <DetailRow label="Booking" value={`#${bookingId}`} />
            <DetailRow
              label="Booking status"
              value={booking ? getBookingStatusLabel(booking.status) : "Unavailable"}
            />
            <DetailRow
              label="Payment status"
              value={payment ? getPaymentStatusLabel(payment.status) : "Unavailable"}
            />
            {payment?.amount != null ? (
              <DetailRow label="Amount" value={formatMoney(payment.amount)} />
            ) : null}
            {payment?.failure_message ? (
              <Text style={styles.errorText}>{payment.failure_message}</Text>
            ) : null}
          </>
        )}

        <View style={styles.actions}>
          <PrimaryButton
            label="Back to bookings"
            onPress={() =>
              navigation.navigate("Main", { screen: "CustomerBookings" })
            }
          />
          <SecondaryButton
            disabled={isLoading}
            label="Refresh result"
            onPress={() => void loadResult()}
          />
        </View>
      </View>
    </ScrollView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    flexGrow: 1,
    justifyContent: "center",
    padding: spacing.lg,
  },
  card: {
    alignSelf: "center",
    gap: spacing.md,
    maxWidth: 560,
    width: "100%",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.xl,
  },
  eyebrow: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "800",
  },
  body: {
    color: colors.mutedText,
    fontSize: 15,
    lineHeight: 22,
  },
  detailRow: {
    gap: spacing.xs,
  },
  detailLabel: {
    color: colors.mutedText,
    fontSize: 13,
    fontWeight: "600",
  },
  detailValue: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
  },
  errorText: {
    color: colors.danger,
    fontSize: 14,
    lineHeight: 20,
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
});
