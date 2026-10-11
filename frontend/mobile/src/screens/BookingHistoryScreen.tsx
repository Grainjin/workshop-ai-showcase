import { useFocusEffect, useNavigation } from "@react-navigation/native";
import { useCallback, useState } from "react";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  appealCustomerRefund,
  cancelCustomerRefund,
  getCustomerBookings,
  getCustomerPayments,
  requestCustomerRefund,
} from "../api/customer";
import { getProviderBookings } from "../api/provider";
import { CompletionProofGallery } from "../components/CompletionProofGallery";
import { CustomerBookingDetailModal } from "../components/CustomerBookingDetailModal";
import { ProviderBookingDetailModal } from "../components/ProviderBookingDetailModal";
import { BookingPriceBreakdown } from "../components/BookingPriceBreakdown";
import { BookingCoreDetails } from "../components/BookingCoreDetails";
import { BookingContextInformation } from "../components/BookingContextInformation";
import { PrimaryButton } from "../components/PrimaryButton";
import { SecondaryButton } from "../components/SecondaryButton";
import { TextField } from "../components/TextField";
import { useAuth } from "../context/AuthContext";
import type { RootStackParamList } from "../navigation/types";
import { colors, radius, spacing } from "../theme/theme";
import type { BookingDetail, PaymentSummary } from "../types/booking";
import { getRefundStatusLabel } from "../constants/labels";
import { formatDateTime } from "../utils/datetime";
import { getErrorMessage } from "../utils/errors";
import { formatMoney } from "../utils/money";
import { useConfirmation } from "../utils/useConfirmation";
import { indexLatestPayments } from "../utils/payment";
import {
  canCustomerRequestRefund,
  shouldShowFinalQuote,
  shouldShowInitialQuote,
  shouldShowInitialQuoteHistory,
} from "../utils/bookingActions";

const HISTORY_ORDER_STATUSES = [
  "completed",
  "refunding",
  "cancelled",
  "rejected",
  "refunded",
  "partially_refunded",
  "visit_completed_closed",
];

export function BookingHistoryScreen() {
  const { user } = useAuth();
  const navigation = useNavigation<
    NativeStackNavigationProp<RootStackParamList>
  >();
  const { confirmationModal, requestConfirmation } = useConfirmation();
  const [bookings, setBookings] = useState<BookingDetail[]>([]);
  const [paymentsByBookingId, setPaymentsByBookingId] = useState<
    Record<number, PaymentSummary>
  >({});
  const [selectedBooking, setSelectedBooking] = useState<BookingDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActing, setIsActing] = useState(false);
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundReason, setRefundReason] = useState("");
  const [refundAppealReason, setRefundAppealReason] = useState("");

  const loadBookings = useCallback(async () => {
    if (!user || user.role === "admin") {
      setBookings([]);
      setPaymentsByBookingId({});
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setMessage("");
    try {
      if (user.role === "provider") {
        const result = await getProviderBookings(undefined, 1, 100);
        setBookings(filterHistoryBookings(result?.items ?? []));
        setPaymentsByBookingId({});
      } else {
        const [bookingResult, paymentResult] = await Promise.all([
          getCustomerBookings(undefined, 1, 100),
          getCustomerPayments(1, 100),
        ]);
        const payments = indexLatestPayments(paymentResult?.items ?? []);
        setBookings(filterHistoryBookings(bookingResult?.items ?? []));
        setPaymentsByBookingId(payments);
      }
    } catch (error) {
      setBookings([]);
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  useFocusEffect(
    useCallback(() => {
      void loadBookings();
    }, [loadBookings]),
  );

  function openProvider(booking: BookingDetail) {
    if (Platform.OS === "web") {
      setSelectedBooking(null);
    }
    navigation.navigate("CustomerProviderDetail", {
      providerId: booking.provider_profile_id,
    });
  }

  function openBooking(booking: BookingDetail) {
    setSelectedBooking(booking);
    setActionError("");
    setRefundAmount("");
    setRefundReason("");
    setRefundAppealReason("");
  }

  async function handleRequestRefund() {
    if (!selectedBooking) {
      return;
    }

    const reason = refundReason.trim();
    if (!reason) {
      setActionError("Enter a refund reason.");
      return;
    }

    const parsedAmount = refundAmount.trim() ? Number(refundAmount) : undefined;
    const paidAmount = paymentsByBookingId[selectedBooking.id]?.amount;
    if (
      parsedAmount !== undefined &&
      (!Number.isFinite(parsedAmount) ||
        parsedAmount <= 0 ||
        (paidAmount != null && parsedAmount > paidAmount))
    ) {
      setActionError("Refund amount must be greater than 0 and no more than the paid amount.");
      return;
    }

    setIsActing(true);
    setActionError("");
    try {
      const result = await requestCustomerRefund(
        selectedBooking.id,
        reason,
        parsedAmount,
      );
      setSelectedBooking(result?.booking ?? selectedBooking);
      setRefundAmount("");
      setRefundReason("");
      setMessage("Refund request sent.");
      await loadBookings();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  async function handleCancelRefund() {
    const refundRequestId = selectedBooking?.current_refund_request?.id;
    if (!refundRequestId) {
      setActionError("This refund request cannot be cancelled.");
      return;
    }

    setIsActing(true);
    setActionError("");
    try {
      const result = await cancelCustomerRefund(refundRequestId);
      setSelectedBooking(result?.booking ?? selectedBooking);
      setMessage("Refund request cancelled.");
      await loadBookings();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  function confirmCancelRefund() {
    requestConfirmation({
      title: "Cancel refund request?",
      message: "The refund request will be withdrawn. You can submit a new request later if the booking remains eligible.",
      onConfirm: () => void handleCancelRefund(),
      confirmLabel: "Cancel refund",
    });
  }

  async function handleAppealRefund() {
    const refundRequestId = selectedBooking?.current_refund_request?.id;
    const reason = refundAppealReason.trim();
    if (!refundRequestId) {
      setActionError("This refund cannot be appealed.");
      return;
    }
    if (!reason) {
      setActionError("Enter an appeal reason.");
      return;
    }

    setIsActing(true);
    setActionError("");
    try {
      const result = await appealCustomerRefund(refundRequestId, reason);
      setSelectedBooking(result?.booking ?? selectedBooking);
      setRefundAppealReason("");
      setMessage("Appeal submitted.");
      await loadBookings();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Booking history</Text>
        <SecondaryButton
          disabled={isLoading}
          label="Refresh"
          onPress={() => void loadBookings()}
        />
      </View>

      {message ? <Text style={styles.errorText}>{message}</Text> : null}

      {isLoading ? (
        <View style={styles.loadingBox}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : bookings.length === 0 ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyTitle}>No booking history</Text>
          <Text style={styles.emptyText}>Completed and cancelled bookings appear here.</Text>
        </View>
      ) : (
        <View style={styles.list}>
          {bookings.map((booking) => (
            <HistoryBookingCard
              booking={booking}
              key={booking.id}
              onPress={() => openBooking(booking)}
              userRole={user?.role}
            />
          ))}
        </View>
      )}

      {user?.role === "provider" ? (
        <ProviderBookingDetailModal
          booking={selectedBooking}
          onClose={() => setSelectedBooking(null)}
          showReadOnly
        />
      ) : (
        <CustomerBookingDetailModal
          actionError={actionError}
          booking={selectedBooking}
          isActing={isActing}
          onAppealRefund={handleAppealRefund}
          onCancelRefund={confirmCancelRefund}
          onOpenProvider={openProvider}
          onClose={() => setSelectedBooking(null)}
          onRequestRefund={handleRequestRefund}
          payment={selectedBooking ? paymentsByBookingId[selectedBooking.id] : null}
          refundAmount={refundAmount}
          refundAppealReason={refundAppealReason}
          refundReason={refundReason}
          setRefundAmount={setRefundAmount}
          setRefundAppealReason={setRefundAppealReason}
          setRefundReason={setRefundReason}
          showInlineRefundFields
        />
      )}

      {confirmationModal}
    </ScrollView>
  );
}

function HistoryBookingCard({
  booking,
  onPress,
  userRole,
}: {
  booking: BookingDetail;
  onPress: () => void;
  userRole?: string;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed ? styles.cardPressed : null]}
    >
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleGroup}>
          <Text style={styles.cardTitle}>{booking.title || `Booking #${booking.id}`}</Text>
          <Text style={styles.targetName}>
            {getTargetName(booking, userRole)}
          </Text>
        </View>
        <Text style={[styles.statusBadge, getStatusBadgeStyle(booking.status)]}>
          {getBookingStatusLabel(booking.status)}
        </Text>
      </View>

      <Text numberOfLines={2} style={styles.description}>
        {booking.service_description}
      </Text>
      <Text numberOfLines={1} style={styles.metaText}>
        {formatDateTime(booking.scheduled_start_time)} -{" "}
        {formatDateTime(booking.scheduled_end_time)}
      </Text>
      <Text numberOfLines={1} style={styles.metaText}>
        {booking.service_address}
      </Text>
      <Text style={styles.amountText}>
        {booking.visit_fee_amount == null
          ? "—"
          : `Visit fee: ${formatMoney(booking.visit_fee_amount)}`}
      </Text>
    </Pressable>
  );
}


function DetailRow({
  label,
  onPress,
  value,
}: {
  label: string;
  onPress?: () => void;
  value: string;
}) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      {onPress ? (
        <Pressable
          accessibilityHint="Opens the provider profile"
          accessibilityLabel={`Open ${value}`}
          accessibilityRole="link"
          onPress={onPress}
        >
          <Text style={[styles.detailValue, styles.detailLink]}>{value}</Text>
        </Pressable>
      ) : (
        <Text style={styles.detailValue}>{value}</Text>
      )}
    </View>
  );

}

function filterHistoryBookings(bookings: BookingDetail[]) {
  return bookings.filter((booking) =>
    HISTORY_ORDER_STATUSES.includes(String(booking.status)),
  );
}

function getTargetName(booking: BookingDetail, userRole?: string) {
  if (userRole === "provider") {
    return booking.customer?.name || `Customer #${booking.customer_id}`;
  }

  return booking.provider?.business_name || `Provider #${booking.provider_profile_id}`;
}

function getBookingStatusLabel(status: string) {
  const labels: Record<string, string> = {
    completed: "Completed",
    cancelled: "Cancelled",
    rejected: "Declined",
    refunded: "Refunded",
    partially_refunded: "Partially refunded",
    visit_completed_closed: "Closed",
  };

  return labels[status] || status;
}

function getStatusBadgeStyle(status: string) {
  if (status === "completed") {
    return styles.statusSuccess;
  }

  return styles.statusMuted;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
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
    fontWeight: "800",
  },
  loadingBox: {
    minHeight: 180,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyCard: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.lg,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  errorText: {
    color: colors.danger,
    fontSize: 14,
    lineHeight: 20,
  },
  refundNotice: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 19,
  },
  list: {
    gap: spacing.md,
  },
  card: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  cardPressed: {
    backgroundColor: colors.surface,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  cardTitleGroup: {
    flex: 1,
    gap: spacing.xs,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "800",
  },
  targetName: {
    color: colors.mutedText,
    fontSize: 14,
  },
  statusBadge: {
    overflow: "hidden",
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    fontSize: 13,
    fontWeight: "700",
  },
  statusSuccess: {
    backgroundColor: "#ECFDF3",
    color: colors.primary,
  },
  statusMuted: {
    backgroundColor: colors.surface,
    color: colors.mutedText,
  },
  description: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  metaText: {
    color: colors.mutedText,
    fontSize: 13,
  },
  amountText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
  },
  modalOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.28)",
  },
  modalCard: {
    maxHeight: "88%",
    gap: spacing.md,
    borderTopLeftRadius: radius.md,
    borderTopRightRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  modalTitle: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "800",
  },
  detailContent: {
    gap: spacing.md,
    paddingBottom: spacing.md,
  },
  detailRow: {
    gap: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingBottom: spacing.sm,
  },
  detailLabel: {
    color: colors.mutedText,
    fontSize: 12,
    fontWeight: "700",
  },
  detailValue: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
  },
  detailLink: {
    color: colors.primary,
    textDecorationLine: "underline",
    fontWeight: "700",
  },
  modalActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
  },
});
