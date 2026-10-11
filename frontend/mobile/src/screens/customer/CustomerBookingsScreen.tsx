import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AppState,
  ActivityIndicator,
  Alert,
  Linking,
  Modal,
  Pressable,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  acceptCustomerBookingQuote,
  acceptCustomerFinalQuote,
  appealCustomerRefund,
  cancelCustomerBooking,
  cancelCustomerBookingAfterVisit,
  cancelCustomerRefund,
  confirmCustomerBookingComplete,
  createCustomerReview,
  getCustomerBookings,
  getCustomerPayments,
  payCustomerBooking,
  rejectCustomerBookingQuote,
  rejectCustomerFinalQuote,
  requestCustomerRefund,
} from "../../api/customer";
import { getBookingById } from "../../api/chat";
import { CustomerReviewModal } from "../../components/CustomerReviewModal";
import { useConfirmation } from "../../utils/useConfirmation";
import { CompletionProofGallery } from "../../components/CompletionProofGallery";
import { CustomerBookingDetailModal } from "../../components/CustomerBookingDetailModal";
import { BookingPriceBreakdown } from "../../components/BookingPriceBreakdown";
import { BookingCoreDetails } from "../../components/BookingCoreDetails";
import { BookingContextInformation } from "../../components/BookingContextInformation";
import { ActionReasonModal } from "../../components/ActionReasonModal";
import { PrimaryButton } from "../../components/PrimaryButton";
import { SecondaryButton } from "../../components/SecondaryButton";
import { TextField } from "../../components/TextField";
import type { RootStackParamList } from "../../navigation/types";
import { colors, radius, spacing } from "../../theme/theme";
import type {
  BookingActionResponseData,
  BookingDetail,
  PaymentSummary,
} from "../../types/booking";
import { getPaymentStatusLabel } from "../../constants/labels";
import { formatDateTime } from "../../utils/datetime";
import { getErrorMessage } from "../../utils/errors";
import { formatMoney, formatPayLabel } from "../../utils/money";
import {
  createPaymentIdempotencyKey,
  getPaymentAction,
  getPaymentStatusTone,
  indexLatestPayments,
  shouldRotatePaymentIdempotencyKey,
} from "../../utils/payment";
import {
  canCustomerCancelBooking,
  canCustomerRequestRefund,
  getCustomerBookingListAction,
  shouldShowFinalQuote,
  shouldShowInitialQuote,
  shouldShowInitialQuoteHistory,
} from "../../utils/bookingActions";
import { createLatestRequestGuard } from "../../utils/latestRequest";
import { resolveBookingReferenceDetail } from "../../utils/referencePrice";

const HIDDEN_ORDER_STATUSES = [
  "completed",
  "cancelled",
  "rejected",
  "refunded",
  "partially_refunded",
  "visit_completed_closed",
];
type ReasonAction = "decline_quote" | "decline_final_quote" | "refund";
export function CustomerBookingsScreen() {
  const navigation = useNavigation<
    NativeStackNavigationProp<RootStackParamList>
  >();
  const { confirmationModal, requestConfirmation } = useConfirmation();
  const openBookingRequestGuard = useRef(createLatestRequestGuard()).current;
  const [bookings, setBookings] = useState<BookingDetail[]>([]);
  const [paymentsByBookingId, setPaymentsByBookingId] = useState<
    Record<number, PaymentSummary>
  >({});
  const [selectedBooking, setSelectedBooking] = useState<BookingDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActing, setIsActing] = useState(false);
  const paymentInFlightRef = useRef(false);
  const paymentIdempotencyKeysRef = useRef<Record<number, string>>({});
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [refundReason, setRefundReason] = useState("");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundAppealReason, setRefundAppealReason] = useState("");
  const [reasonAction, setReasonAction] = useState<ReasonAction | null>(null);
  const [reviewBooking, setReviewBooking] = useState<BookingDetail | null>(null);
  const [reviewError, setReviewError] = useState("");
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  const loadBookings = useCallback(async () => {
    setMessage("");
    try {
      const [result, paymentResult] = await Promise.all([
        getCustomerBookings(undefined, 1, 100),
        getCustomerPayments(1, 100),
      ]);
      const payments = paymentResult?.items ?? [];
      payments.forEach((payment) => {
        if (shouldRotatePaymentIdempotencyKey(payment)) {
          delete paymentIdempotencyKeysRef.current[payment.booking_id];
        }
      });
      setBookings(filterActiveBookings(result?.items ?? []));
      setPaymentsByBookingId(indexLatestPayments(payments));
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }, []);

  useEffect(() => {
    let isActive = true;

    async function loadInitialBookings() {
      setIsLoading(true);
      try {
        const [result, paymentResult] = await Promise.all([
          getCustomerBookings(undefined, 1, 100),
          getCustomerPayments(1, 100),
        ]);
        if (isActive) {
          const payments = paymentResult?.items ?? [];
          payments.forEach((payment) => {
            if (shouldRotatePaymentIdempotencyKey(payment)) {
              delete paymentIdempotencyKeysRef.current[payment.booking_id];
            }
          });
          setBookings(filterActiveBookings(result?.items ?? []));
          setPaymentsByBookingId(indexLatestPayments(payments));
        }
      } catch (error) {
        if (isActive) {
          setMessage(getErrorMessage(error));
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadInitialBookings();

    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    let previousState = AppState.currentState;
    const subscription = AppState.addEventListener("change", (nextState) => {
      if (
        previousState.match(/inactive|background/) &&
        nextState === "active"
      ) {
        void loadBookings();
      }
      previousState = nextState;
    });

    return () => subscription.remove();
  }, [loadBookings]);

  useFocusEffect(
    useCallback(() => {
      void loadBookings();
    }, [loadBookings]),
  );

  useEffect(
    () => () => openBookingRequestGuard.invalidate(),
    [openBookingRequestGuard],
  );

  async function openBooking(booking: BookingDetail) {
    const requestGeneration = openBookingRequestGuard.begin();
    const detail = await resolveBookingReferenceDetail(booking, getBookingById);
    if (!openBookingRequestGuard.isLatest(requestGeneration)) return;
    setSelectedBooking(detail);
    setRejectReason("");
    setRefundReason("");
    setRefundAmount("");
    setRefundAppealReason("");
    setActionError("");
    setReasonAction(null);
  }

  function updateSelectedBooking(booking: BookingDetail) {
    setSelectedBooking((current) => ({
      ...booking,
      reference_price_range:
        booking.reference_price_range ?? current?.reference_price_range,
    }));
  }

  function closeBooking() {
    openBookingRequestGuard.invalidate();
    setSelectedBooking(null);
    setRejectReason("");
    setRefundReason("");
    setRefundAmount("");
    setRefundAppealReason("");
    setActionError("");
    setReasonAction(null);
  }

  async function openReasonDialog(booking: BookingDetail, action: ReasonAction) {
    const requestGeneration = openBookingRequestGuard.begin();
    const detail = await resolveBookingReferenceDetail(booking, getBookingById);
    if (!openBookingRequestGuard.isLatest(requestGeneration)) return;
    setSelectedBooking(detail);
    setReasonAction(action);
    setActionError("");
  }

  function confirmReasonAction() {
    if (!selectedBooking || !reasonAction) {
      return;
    }
    if (!rejectReason.trim() && reasonAction !== "refund") {
      setActionError("Enter a reason for declining the quote.");
      return;
    }
    if (reasonAction === "refund" && !refundReason.trim()) {
      setActionError("Enter a refund reason.");
      return;
    }
    if (reasonAction === "refund") {
      const parsedAmount = refundAmount.trim() ? Number(refundAmount) : undefined;
      const paidAmount = paymentsByBookingId[selectedBooking.id]?.amount ?? selectedBooking.quote_amount;
      if (
        parsedAmount !== undefined &&
        (!Number.isFinite(parsedAmount) || parsedAmount <= 0 || (paidAmount != null && parsedAmount > paidAmount))
      ) {
        setActionError("Refund amount must be greater than 0 and no more than the paid amount.");
        return;
      }
    }
    const action = reasonAction;
    setReasonAction(null);
    if (action === "decline_quote") {
      void handleRejectQuote(selectedBooking);
    } else if (action === "decline_final_quote") {
      void handleRejectFinalQuote(selectedBooking);
    } else {
      void handleRequestRefund(selectedBooking);
    }
  }

  async function runBookingAction(
    action: () => Promise<BookingActionResponseData | null | undefined>,
    successMessage: string,
  ) {
    setIsActing(true);
    setActionError("");
    try {
      const result = await action();
      if (result?.booking) {
        updateSelectedBooking(
          await resolveBookingReferenceDetail(result.booking, getBookingById),
        );
      }
      await loadBookings();
      Alert.alert("Success", successMessage);
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  async function handleAcceptQuote(booking: BookingDetail) {
    await runBookingAction(
      () => acceptCustomerBookingQuote(booking.id),
      "Quote accepted. Payment is due.",
    );
  }

  async function handleRejectQuote(booking: BookingDetail) {
    const reason = rejectReason.trim();
    if (!reason) {
      setActionError("Enter a reason for declining the quote.");
      return;
    }

    await runBookingAction(
      () => rejectCustomerBookingQuote(booking.id, reason),
      "Quote declined. The provider can send a new quote.",
    );
  }

  async function handleAcceptFinalQuote(booking: BookingDetail) {
    await runBookingAction(
      () => acceptCustomerFinalQuote(booking.id),
      "Final quote accepted. Service payment is due.",
    );
  }

  async function handleRejectFinalQuote(booking: BookingDetail) {
    const reason = rejectReason.trim();
    if (!reason) {
      setActionError("Enter a reason for declining the final quote.");
      return;
    }
    await runBookingAction(
      () => rejectCustomerFinalQuote(booking.id, reason),
      "Final quote declined. The provider can submit a revised quote.",
    );
  }

  async function handlePayBooking(booking: BookingDetail) {
    if (paymentInFlightRef.current) {
      return;
    }

    paymentInFlightRef.current = true;
    setIsActing(true);
    setActionError("");
    try {
      const idempotencyKey =
        paymentIdempotencyKeysRef.current[booking.id] ??
        (paymentIdempotencyKeysRef.current[booking.id] =
          createPaymentIdempotencyKey());
      const paymentStage =
        booking.status === "awaiting_service_payment" ? "service_fee" : "visit_fee";
      const result = await payCustomerBooking(
        booking.id,
        "iyzico_checkout",
        idempotencyKey,
        paymentStage,
      );
      const payment = result?.payment;
      if (result?.booking) {
        updateSelectedBooking(
          await resolveBookingReferenceDetail(result.booking, getBookingById),
        );
      }
      if (payment) {
        setPaymentsByBookingId((current) => ({
          ...current,
          [payment.booking_id]: payment,
        }));
      }

      if (shouldRotatePaymentIdempotencyKey(payment)) {
        delete paymentIdempotencyKeysRef.current[booking.id];
      }

      if (result?.payment_page_url) {
        delete paymentIdempotencyKeysRef.current[booking.id];
        await Linking.openURL(result.payment_page_url);
        setMessage("iyzico checkout opened. Return here after payment to refresh the status.");
        void loadBookings();
      } else if (payment?.status) {
        setMessage(`Payment status: ${getPaymentStatusLabel(payment.status)}.`);
      } else {
        setMessage("Payment checkout is being prepared. Refresh this page shortly.");
      }
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      paymentInFlightRef.current = false;
      setIsActing(false);
    }
  }

  function openProvider(booking: BookingDetail) {
    if (Platform.OS === "web") {
      closeBooking();
    }
    navigation.navigate("CustomerProviderDetail", {
      providerId: booking.provider_profile_id,
    });
  }

  async function handleCancelBooking(booking: BookingDetail) {
    await runBookingAction(
      () => cancelCustomerBooking(booking.id),
      "Booking cancelled.",
    );
  }

  async function handleCancelAfterVisit(booking: BookingDetail) {
    await runBookingAction(
      () => cancelCustomerBookingAfterVisit(booking.id),
      "Booking cancelled.",
    );
  }

  function confirmCancelBooking(booking: BookingDetail) {
    requestConfirmation({
      title: "Cancel booking?",
      message: "This booking will be cancelled and this action cannot be undone. Any paid amount will not be refunded automatically. If you need a refund, use the refund process separately.",
      onConfirm: () => void handleCancelBooking(booking),
      confirmLabel: "Cancel",
    });
  }

  function confirmCancelAfterVisit(booking: BookingDetail) {
    requestConfirmation({
      title: "Cancel booking?",
      message: "The booking will be closed without requesting a refund. Any paid amount will not be refunded automatically. If you need a refund, use the refund process separately.",
      onConfirm: () => void handleCancelAfterVisit(booking),
      confirmLabel: "Cancel",
    });
  }

  async function handleRequestRefund(booking: BookingDetail) {
    const reason = refundReason.trim();
    if (!reason) {
      setActionError("Enter a refund reason.");
      return;
    }

    const parsedAmount = refundAmount.trim() ? Number(refundAmount) : undefined;
    const paidAmount = paymentsByBookingId[booking.id]?.amount ?? booking.quote_amount;
    if (
      parsedAmount !== undefined &&
      (!Number.isFinite(parsedAmount) ||
        parsedAmount <= 0 ||
        (paidAmount != null && parsedAmount > paidAmount))
    ) {
      setActionError("Refund amount must be greater than 0 and no more than the paid amount.");
      return;
    }

    await runBookingAction(
      () =>
        requestCustomerRefund(
          booking.id,
          reason,
          parsedAmount,
        ),
      "Refund request sent.",
    );
  }

  async function handleCancelRefund(booking: BookingDetail) {
    const refundRequestId = booking.current_refund_request?.id;
    if (!refundRequestId) {
      setActionError("This refund request cannot be cancelled.");
      return;
    }

    await runBookingAction(
      () => cancelCustomerRefund(refundRequestId),
      "Refund request cancelled.",
    );
  }

  async function handleAppealRefund(booking: BookingDetail) {
    const refundRequestId = booking.current_refund_request?.id;
    const reason = refundAppealReason.trim();
    if (!refundRequestId) {
      setActionError("This refund cannot be appealed.");
      return;
    }
    if (!reason) {
      setActionError("Enter an appeal reason.");
      return;
    }

    await runBookingAction(
      () => appealCustomerRefund(refundRequestId, reason),
      "Appeal submitted.",
    );
  }

  async function handleConfirmComplete(booking: BookingDetail) {
    setIsActing(true);
    setActionError("");
    try {
      const result = await confirmCustomerBookingComplete(booking.id);
      if (result?.payment_page_url) {
        updateSelectedBooking(
          await resolveBookingReferenceDetail(
            result.booking ?? booking,
            getBookingById,
          ),
        );
        await Linking.openURL(result.payment_page_url);
        setMessage("The final quote changed. Complete the new authorization, then confirm again.");
        await loadBookings();
        return;
      }
      setSelectedBooking(null);
      await loadBookings();
      setReviewError("");
      setReviewBooking(
        result?.booking ?? {
          ...booking,
          status: "completed",
        },
      );
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  function confirmCancelRefund(booking: BookingDetail) {
    requestConfirmation({
      title: "Cancel refund request?",
      message: "The refund request will be withdrawn. You can submit a new request later if the booking remains eligible.",
      onConfirm: () => void handleCancelRefund(booking),
      confirmLabel: "Cancel refund",
    });
  }

  async function handleSubmitReview(rating: number, comment: string) {
    if (!reviewBooking) {
      return;
    }

    setIsSubmittingReview(true);
    setReviewError("");
    try {
      await createCustomerReview(reviewBooking.id, rating, comment);
      setReviewBooking(null);
      Alert.alert("Review submitted", "Thank you for your feedback.");
    } catch (error) {
      setReviewError(getErrorMessage(error));
    } finally {
      setIsSubmittingReview(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Bookings</Text>
        <SecondaryButton
          disabled={isLoading || isActing}
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
          <Text style={styles.emptyTitle}>No bookings yet</Text>
          <Text style={styles.emptyText}>Active bookings appear here.</Text>
        </View>
      ) : (
        <View style={styles.list}>
          {bookings.map((booking) => (
            <BookingCard
              booking={booking}
              payment={paymentsByBookingId[booking.id]}
              disabled={isActing}
              key={booking.id}
              onAcceptQuote={handleAcceptQuote}
              onAcceptFinalQuote={handleAcceptFinalQuote}
              onConfirmComplete={handleConfirmComplete}
              onOpen={openBooking}
              onPay={handlePayBooking}
            />
          ))}
        </View>
      )}

      <CustomerBookingDetailModal
        actionError={actionError}
        booking={selectedBooking}
        payment={selectedBooking ? paymentsByBookingId[selectedBooking.id] : null}
        isActing={isActing}
        onAcceptQuote={() => selectedBooking && void handleAcceptQuote(selectedBooking)}
        onAcceptFinalQuote={() => selectedBooking && void handleAcceptFinalQuote(selectedBooking)}
        onAppealRefund={() => selectedBooking && void handleAppealRefund(selectedBooking)}
        onCancel={() => selectedBooking && confirmCancelBooking(selectedBooking)}
        onCancelAfterVisit={() => selectedBooking && confirmCancelAfterVisit(selectedBooking)}
        onCancelRefund={() => selectedBooking && confirmCancelRefund(selectedBooking)}
        onClose={closeBooking}
        onConfirmComplete={() => selectedBooking && void handleConfirmComplete(selectedBooking)}
        onPay={() => selectedBooking && void handlePayBooking(selectedBooking)}
        onOpenProvider={openProvider}
        onRejectQuote={() => selectedBooking && void openReasonDialog(selectedBooking, "decline_quote")}
        onRejectFinalQuote={() => selectedBooking && void openReasonDialog(selectedBooking, "decline_final_quote")}
        onRequestRefund={() => selectedBooking && void openReasonDialog(selectedBooking, "refund")}
        refundAppealReason={refundAppealReason}
        refundAmount={refundAmount}
        refundReason={refundReason}
        setRefundAppealReason={setRefundAppealReason}
        setRefundAmount={(value) => {
          setRefundAmount(value);
          setActionError("");
        }}
        setRefundReason={setRefundReason}
      />

      {selectedBooking && reasonAction ? (
        <ActionReasonModal
          amount={refundAmount}
          amountLabel="Refund amount (optional)"
          confirmLabel={reasonAction === "refund" ? "Request refund" : "Submit decline"}
          onCancel={() => setReasonAction(null)}
          onChangeAmount={reasonAction === "refund" ? setRefundAmount : undefined}
          onChangeReason={reasonAction === "refund" ? setRefundReason : setRejectReason}
          onConfirm={confirmReasonAction}
          reason={reasonAction === "refund" ? refundReason : rejectReason}
          reasonLabel={reasonAction === "refund" ? "Refund reason" : "Decline reason"}
          title={
            reasonAction === "refund"
              ? "Request a refund"
              : reasonAction === "decline_final_quote"
                ? "Decline final quote"
                : "Decline quote"
          }
          error={actionError}
        />
      ) : null}

      {confirmationModal}

      <CustomerReviewModal
        booking={reviewBooking}
        errorMessage={reviewError}
        isSubmitting={isSubmittingReview}
        onClose={() => setReviewBooking(null)}
        onSubmit={(rating, comment) => void handleSubmitReview(rating, comment)}
      />
    </ScrollView>
  );
}

function BookingCard({
  booking,
  disabled,
  payment,
  onAcceptQuote,
  onAcceptFinalQuote,
  onConfirmComplete,
  onOpen,
  onPay,
}: {
  booking: BookingDetail;
  disabled: boolean;
  payment?: PaymentSummary | null;
  onAcceptQuote: (booking: BookingDetail) => void;
  onAcceptFinalQuote: (booking: BookingDetail) => void;
  onConfirmComplete: (booking: BookingDetail) => void;
  onOpen: (booking: BookingDetail) => void;
  onPay: (booking: BookingDetail) => void;
}) {
  const listAction = getCustomerBookingListAction(booking, payment);
  const paymentAction = getPaymentAction(booking.status, payment);
  const payableAmount =
    booking.status === "awaiting_service_payment"
      ? booking.final_quote_amount ?? booking.quote_amount
      : booking.visit_fee_amount ?? booking.quote_amount;
  const payableLabel =
    booking.status === "awaiting_service_payment" ? "Service amount" : "Visit fee";
  const showAcceptedFinalQuoteAmounts =
    [
      "awaiting_service_payment",
      "service_paid",
      "awaiting_confirmation",
      "accepted",
    ].includes(String(booking.status)) && booking.final_quote_amount != null;

  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => onOpen(booking)}
      style={({ pressed }) => [styles.card, pressed ? styles.cardPressed : null]}
    >
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleGroup}>
          <Text style={styles.cardTitle}>{booking.title || `Booking #${booking.id}`}</Text>
          <Text style={styles.providerName}>
            {booking.provider?.business_name || `Provider #${booking.provider_profile_id}`}
          </Text>
        </View>
        <View style={styles.statusStack}>
          <Text style={[styles.statusBadge, getStatusBadgeStyle(booking.status)]}>
            {getBookingStatusLabel(booking.status)}
          </Text>
          {payment ? (
            <Text
              style={[
                styles.statusBadge,
                getPaymentBadgeStyle(payment.status),
              ]}
            >
              {getPaymentStatusLabel(payment.status)}
            </Text>
          ) : null}
        </View>
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
      {showAcceptedFinalQuoteAmounts ? (
        <>
          <Text style={styles.amountText}>
            {booking.visit_fee_amount == null
              ? "Awaiting visit fee"
              : `Visit fee: ${formatMoney(booking.visit_fee_amount)}`}
          </Text>
          <Text style={styles.amountText}>
            Service amount: {formatMoney(booking.final_quote_amount ?? 0)}
          </Text>
        </>
      ) : (
        <Text style={styles.amountText}>
          {payableAmount == null
            ? booking.status === "awaiting_service_payment"
              ? "Awaiting service amount"
              : "Awaiting visit fee"
            : `${payableLabel}: ${formatMoney(payableAmount)}`}
        </Text>
      )}
      {booking.current_refund_request ? (
        <Text style={styles.refundText}>
          Refund: {getRefundStatusLabel(booking.current_refund_request.status)}
        </Text>
      ) : null}

      {listAction ? (
        <View style={styles.cardActions}>
          {listAction === "accept_quote" ? (
            <PrimaryButton
              disabled={disabled}
              label="Accept quote"
              onPress={() => onAcceptQuote(booking)}
            />
          ) : null}
          {listAction === "accept_final_quote" ? (
            <PrimaryButton
              disabled={disabled}
              label="Accept final quote"
              onPress={() => onAcceptFinalQuote(booking)}
            />
          ) : null}
          {listAction === "confirm_complete" ? (
            <PrimaryButton
              disabled={disabled}
              label="Confirm complete"
              onPress={() => onConfirmComplete(booking)}
            />
          ) : null}
          {listAction === "pay" ? (
            <PrimaryButton
              disabled={disabled}
              label={
                paymentAction === "continue"
                  ? "Continue payment"
                  : formatPayLabel(payableAmount)
              }
              onPress={() => onPay(booking)}
            />
          ) : null}
        </View>
      ) : null}
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

function getBookingStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "Pending review",
    quoted: "Quote awaiting confirmation",
    awaiting_payment: "Awaiting payment",
    accepted: "In progress",
    rejected: "Declined",
    refunding: "Refund in progress",
    refunded: "Refunded",
    partially_refunded: "Partially refunded",
    awaiting_confirmation: "Awaiting confirmation",
    completed: "Completed",
    cancelled: "Cancelled",
  };

  return labels[status] || status;
}

function getRefundStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "Pending",
    approved: "Approved",
    rejected: "Declined",
    appealed: "Under review",
    admin_rejected: "Appeal declined",
    cancelled: "Cancelled",
  };

  return labels[status] || status;
}

function filterActiveBookings(bookings: BookingDetail[]) {
  return bookings.filter(
    (booking) => !HIDDEN_ORDER_STATUSES.includes(String(booking.status)),
  );
}

function getStatusBadgeStyle(status: string) {
  if (status === "awaiting_payment") {
    return styles.statusWarning;
  }
  if (status === "accepted" || status === "completed") {
    return styles.statusSuccess;
  }
  if (
    status === "cancelled" ||
    status === "rejected" ||
    status === "refunded" ||
    status === "partially_refunded"
  ) {
    return styles.statusMuted;
  }
  return styles.statusNeutral;
}

function getPaymentBadgeStyle(status: string) {
  const tone = getPaymentStatusTone(status);
  if (tone === "success") {
    return styles.statusSuccess;
  }
  if (tone === "danger") {
    return styles.statusDanger;
  }
  if (tone === "muted") {
    return styles.statusMuted;
  }
  return styles.statusWarning;
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
  payHint: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 19,
  },
  actionHint: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 19,
  },
  actionErrorText: {
    color: colors.danger,
    fontSize: 14,
    lineHeight: 20,
    paddingHorizontal: spacing.xs,
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
  statusStack: {
    alignItems: "flex-end",
    gap: spacing.xs,
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
  providerName: {
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
  statusNeutral: {
    backgroundColor: "#EEF2FF",
    color: "#3730A3",
  },
  statusWarning: {
    backgroundColor: "#FFF7ED",
    color: "#C2410C",
  },
  statusSuccess: {
    backgroundColor: "#ECFDF3",
    color: colors.primary,
  },
  statusMuted: {
    backgroundColor: colors.surface,
    color: colors.mutedText,
  },
  statusDanger: {
    backgroundColor: "#FEF2F2",
    color: colors.danger,
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
  refundText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: "600",
  },
  cardActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: spacing.sm,
    paddingTop: spacing.xs,
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
  },
  detailLabel: {
    color: colors.mutedText,
    fontSize: 13,
    fontWeight: "600",
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
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
  stageBox: {
    gap: spacing.sm,
  },
  stageOptions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  stageButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  stageButtonActive: {
    borderColor: colors.primary,
    backgroundColor: "#ECFDF3",
  },
  stageButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  stageButtonTextActive: {
    color: colors.primary,
  },
});
