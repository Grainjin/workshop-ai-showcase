import * as ImagePicker from "expo-image-picker";
import { useFocusEffect } from "@react-navigation/native";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  approveProviderRefundRequest,
  completeProviderBooking,
  getProviderBookings,
  getProviderPayments,
  quoteProviderBooking,
  startProviderVisit,
  submitProviderFinalQuote,
  rejectProviderRefundRequest,
  rejectProviderBooking,
} from "../../api/provider";
import { getBookingById } from "../../api/chat";
import { PrimaryButton } from "../../components/PrimaryButton";
import { MarketplaceBreakdownCard } from "../../components/MarketplaceBreakdownCard";
import { ProviderBookingDetailModal as SharedProviderBookingDetailModal } from "../../components/ProviderBookingDetailModal";
import { BookingPriceBreakdown } from "../../components/BookingPriceBreakdown";
import { BookingCoreDetails } from "../../components/BookingCoreDetails";
import { BookingContextInformation } from "../../components/BookingContextInformation";
import { ActionReasonModal } from "../../components/ActionReasonModal";
import { SecondaryButton } from "../../components/SecondaryButton";
import { TextField } from "../../components/TextField";
import { DEMO_MODE } from "../../config/env";
import { colors, radius, spacing } from "../../theme/theme";
import type {
  BookingDetail,
  BookingUploadFile,
  PaymentHistoryEntry,
} from "../../types/booking";
import { formatDateTime } from "../../utils/datetime";
import { getErrorMessage } from "../../utils/errors";
import { formatMoney } from "../../utils/money";
import { indexLatestPayments } from "../../utils/payment";
import { createLatestRequestGuard } from "../../utils/latestRequest";
import { resolveBookingReferenceDetail } from "../../utils/referencePrice";
import {
  shouldShowFinalQuote,
  shouldShowInitialQuote,
  shouldShowInitialQuoteHistory,
} from "../../utils/bookingActions";

const HIDDEN_ORDER_STATUSES = [
  "completed",
  "cancelled",
  "rejected",
  "refunded",
  "partially_refunded",
  "visit_completed_closed",
];
type ProviderReasonAction = "reject_booking" | "reject_refund";

export function ProviderBookingsScreen() {
  const openBookingRequestGuard = useRef(createLatestRequestGuard()).current;
  const [bookings, setBookings] = useState<BookingDetail[]>([]);
  const [paymentsByBookingId, setPaymentsByBookingId] = useState<
    Record<number, PaymentHistoryEntry>
  >({});
  const [selectedBooking, setSelectedBooking] = useState<BookingDetail | null>(null);
  const [selectedPayment, setSelectedPayment] = useState<PaymentHistoryEntry | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActing, setIsActing] = useState(false);
  const [message, setMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [quoteAmountError, setQuoteAmountError] = useState("");
  const [visitFeeError, setVisitFeeError] = useState("");
  const [quoteAmount, setQuoteAmount] = useState("");
  const [visitFeeAmount, setVisitFeeAmount] = useState("");
  const [quoteMessage, setQuoteMessage] = useState("");
  const [quoteFiles, setQuoteFiles] = useState<BookingUploadFile[]>([]);
  const [quoteFilesError, setQuoteFilesError] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [refundRejectReason, setRefundRejectReason] = useState("");
  const [reasonAction, setReasonAction] = useState<ProviderReasonAction | null>(null);
  const [proofAssets, setProofAssets] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [finalQuoteAmount, setFinalQuoteAmount] = useState("");
  const [finalQuoteMessage, setFinalQuoteMessage] = useState("");

  const loadBookings = useCallback(async () => {
    setMessage("");
    try {
      const [bookingResult, paymentResult] = await Promise.all([
        getProviderBookings(undefined, 1, 100),
        getProviderPayments(1, 100),
      ]);
      setBookings(filterActiveBookings(bookingResult?.items ?? []));
      setPaymentsByBookingId(indexLatestPayments(paymentResult?.items ?? []));
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }, []);

  useEffect(() => {
    let isActive = true;

    async function loadInitialBookings() {
      setIsLoading(true);
      try {
        const [bookingResult, paymentResult] = await Promise.all([
          getProviderBookings(undefined, 1, 100),
          getProviderPayments(1, 100),
        ]);
        if (isActive) {
          setBookings(filterActiveBookings(bookingResult?.items ?? []));
          setPaymentsByBookingId(indexLatestPayments(paymentResult?.items ?? []));
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
    setSelectedPayment(paymentsByBookingId[booking.id] ?? null);
    setQuoteAmount(
      detail.expected_service_amount == null
        ? detail.quote_amount == null
          ? ""
          : String(detail.quote_amount)
        : String(detail.expected_service_amount),
    );
    setVisitFeeAmount(
      detail.visit_fee_amount == null ? "" : String(detail.visit_fee_amount),
    );
    setQuoteMessage(detail.quote_message || "");
    setQuoteFiles([]);
    setQuoteFilesError("");
    setRejectReason("");
    setRefundRejectReason("");
    setProofAssets([]);
    setFinalQuoteAmount(
      detail.status === "awaiting_final_quote" && detail.final_quote_declined_at
        ? ""
        : detail.final_quote_amount == null
          ? ""
          : String(detail.final_quote_amount),
    );
    setFinalQuoteMessage(
      detail.status === "awaiting_final_quote" && detail.final_quote_declined_at
        ? ""
        : detail.final_quote_message || "",
    );
    setActionError("");
    setQuoteAmountError("");
    setVisitFeeError("");
  }

  function closeBooking() {
    openBookingRequestGuard.invalidate();
    setSelectedBooking(null);
    setSelectedPayment(null);
    setQuoteAmount("");
    setVisitFeeAmount("");
    setQuoteMessage("");
    setQuoteFiles([]);
    setQuoteFilesError("");
    setRejectReason("");
    setRefundRejectReason("");
    setProofAssets([]);
    setFinalQuoteAmount("");
    setFinalQuoteMessage("");
    setActionError("");
    setQuoteAmountError("");
    setVisitFeeError("");
  }

  async function handleQuoteBooking() {
    if (!selectedBooking) {
      return;
    }

    const amount = Number(quoteAmount);
    const visitFee = Number(visitFeeAmount);
    setQuoteAmountError("");
    setVisitFeeError("");
    if (!Number.isFinite(amount) || amount <= 0) {
      setQuoteAmountError("Enter an expected service amount greater than 0.");
      return;
    }
    if (!Number.isFinite(visitFee) || visitFee <= 0) {
      setVisitFeeError("Enter a visit fee greater than 0.");
      return;
    }
    if (visitFee > amount) {
      setVisitFeeError("Visit fee cannot exceed the expected service amount.");
      return;
    }

    setIsActing(true);
    setActionError("");
    try {
      const result = await quoteProviderBooking(
        selectedBooking.id,
        amount,
        quoteMessage.trim() || null,
        visitFee,
        quoteFiles,
      );
      if (result?.booking) {
        setSelectedBooking(result.booking);
      }
      await loadBookings();
      Alert.alert("Quote sent", "The customer has been notified.");
      closeBooking();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (errorMessage.toLowerCase().includes("visit fee cannot exceed")) {
        setVisitFeeError(errorMessage);
      } else if (/file|attachment/i.test(errorMessage)) {
        setQuoteFilesError(errorMessage);
      } else {
        setActionError(errorMessage);
      }
    } finally {
      setIsActing(false);
    }
  }

  async function handleRejectBooking() {
    if (!selectedBooking) {
      return;
    }

    const reason = rejectReason.trim();
    if (!reason) {
      setActionError("Enter a reason for declining this booking.");
      return;
    }

    setIsActing(true);
    setActionError("");
    try {
      const result = await rejectProviderBooking(selectedBooking.id, reason);
      if (result?.booking) {
        setSelectedBooking(result.booking);
      }
      await loadBookings();
      Alert.alert("Booking declined", "The customer has been notified.");
      closeBooking();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  async function handlePickCompletionProof() {
    setActionError("");

    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setActionError("Allow access to photos to attach completion proof.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      allowsMultipleSelection: true,
      mediaTypes: ["images", "videos"],
      quality: 0.85,
      videoQuality: ImagePicker.UIImagePickerControllerQualityType.Medium,
    });

    if (result.canceled || result.assets.length === 0) {
      return;
    }

    setProofAssets(result.assets);
  }

  async function handleCompleteBooking() {
    if (!selectedBooking) {
      return;
    }
    if (!DEMO_MODE && proofAssets.length === 0) {
      setActionError("Add at least one photo or video as completion proof.");
      return;
    }
    setIsActing(true);
    setActionError("");
    try {
      const result = await completeProviderBooking(
        selectedBooking.id,
        proofAssets.map((asset) => ({
          uri: asset.uri,
          fileName: asset.fileName,
          mimeType: asset.mimeType,
        })),
        null,
        null,
      );
      if (result?.booking) {
        setSelectedBooking(result.booking);
      }
      await loadBookings();
      Alert.alert("Marked complete", "Waiting for the customer to confirm.");
      closeBooking();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  async function handleStartVisit() {
    if (!selectedBooking || (!DEMO_MODE && proofAssets.length === 0)) {
      setActionError("Add at least one arrival photo or video.");
      return;
    }
    setIsActing(true);
    setActionError("");
    setReasonAction(null);
    try {
      await startProviderVisit(selectedBooking.id, proofAssets.map((asset) => ({
        uri: asset.uri,
        fileName: asset.fileName,
        mimeType: asset.mimeType,
      })));
      await loadBookings();
      closeBooking();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (errorMessage.toLowerCase().includes("visit fee cannot exceed")) {
        setVisitFeeError(errorMessage);
      } else {
        setActionError(errorMessage);
      }
    } finally {
      setIsActing(false);
    }
  }

  async function handleSubmitFinalQuote() {
    if (!selectedBooking) return;
    const amount = Number(finalQuoteAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setActionError("Enter a final quote amount greater than 0.");
      return;
    }
    setIsActing(true);
    setActionError("");
    setReasonAction(null);
    try {
      await submitProviderFinalQuote(
        selectedBooking.id,
        amount,
        finalQuoteMessage.trim() || null,
        quoteFiles,
      );
      await loadBookings();
      closeBooking();
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (/file|attachment/i.test(errorMessage)) {
        setQuoteFilesError(errorMessage);
      } else {
        setActionError(errorMessage);
      }
    } finally {
      setIsActing(false);
    }
  }

  async function handleApproveRefund() {
    const refundRequestId = selectedBooking?.current_refund_request?.id;
    if (!refundRequestId) {
      setActionError("No refund request to review.");
      return;
    }

    setIsActing(true);
    setActionError("");
    try {
      const result = await approveProviderRefundRequest(refundRequestId);
      if (result?.booking) {
        setSelectedBooking(result.booking);
      }
      await loadBookings();
      Alert.alert("Refund approved", "This booking is now closed.");
      closeBooking();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
    }
  }

  async function handleRejectRefund() {
    const refundRequestId = selectedBooking?.current_refund_request?.id;
    const reason = refundRejectReason.trim();
    if (!refundRequestId) {
      setActionError("No refund request to review.");
      return;
    }
    if (!reason) {
      setActionError("Enter a reason for declining the refund.");
      return;
    }

    setIsActing(true);
    setActionError("");
    try {
      const result = await rejectProviderRefundRequest(refundRequestId, reason);
      if (result?.booking) {
        setSelectedBooking(result.booking);
      }
      await loadBookings();
      Alert.alert("Refund declined", "The booking remains in refund review.");
      closeBooking();
    } catch (error) {
      setActionError(getErrorMessage(error));
    } finally {
      setIsActing(false);
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
            <ProviderBookingCard
              booking={booking}
              key={booking.id}
              onOpen={openBooking}
            />
          ))}
        </View>
      )}

      <SharedProviderBookingDetailModal
        actionError={actionError}
        quoteAmountError={quoteAmountError}
        visitFeeError={visitFeeError}
        booking={selectedBooking}
        payment={selectedPayment}
        isActing={isActing}
        onClose={closeBooking}
        onApproveRefund={handleApproveRefund}
        onComplete={handleCompleteBooking}
        onStartVisit={handleStartVisit}
        onSubmitFinalQuote={handleSubmitFinalQuote}
        onPickCompletionProof={handlePickCompletionProof}
        onQuote={handleQuoteBooking}
        onReject={() => setReasonAction("reject_booking")}
        onRejectRefund={() => setReasonAction("reject_refund")}
        proofAssets={proofAssets}
        quoteFiles={quoteFiles}
        quoteFilesError={quoteFilesError}
        finalQuoteAmount={finalQuoteAmount}
        finalQuoteMessage={finalQuoteMessage}
        quoteAmount={quoteAmount}
        visitFeeAmount={visitFeeAmount}
        quoteMessage={quoteMessage}
        refundRejectReason={refundRejectReason}
        rejectReason={rejectReason}
        setRefundRejectReason={setRefundRejectReason}
        setQuoteAmount={(value) => {
          setQuoteAmount(value);
          setQuoteAmountError("");
        }}
        setVisitFeeAmount={(value) => {
          setVisitFeeAmount(value);
          setVisitFeeError("");
        }}
        setQuoteMessage={setQuoteMessage}
        setQuoteFiles={(files) => {
          setQuoteFiles(files);
          setQuoteFilesError("");
        }}
        setFinalQuoteAmount={setFinalQuoteAmount}
        setFinalQuoteMessage={setFinalQuoteMessage}
        setRejectReason={setRejectReason}
      />

      {selectedBooking && reasonAction ? (
        <ActionReasonModal
          confirmLabel="Submit"
          onCancel={() => setReasonAction(null)}
          onChangeReason={(value) => {
            if (reasonAction === "reject_booking") {
              setRejectReason(value);
            } else {
              setRefundRejectReason(value);
            }
            setActionError("");
          }}
          onConfirm={() => {
            const action = reasonAction;
            setReasonAction(null);
            if (action === "reject_booking") {
              void handleRejectBooking();
            } else {
              void handleRejectRefund();
            }
          }}
          reason={reasonAction === "reject_booking" ? rejectReason : refundRejectReason}
          reasonLabel="Reason"
          title={reasonAction === "reject_booking" ? "Decline booking" : "Reject refund"}
          error={actionError}
        />
      ) : null}
    </ScrollView>
  );
}

function ProviderBookingCard({
  booking,
  onOpen,
}: {
  booking: BookingDetail;
  onOpen: (booking: BookingDetail) => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => onOpen(booking)}
      style={({ pressed }) => [styles.card, pressed ? styles.cardPressed : null]}
    >
      <View style={styles.cardHeader}>
        <View style={styles.cardTitleGroup}>
          <Text style={styles.cardTitle}>{booking.title || `Booking #${booking.id}`}</Text>
          <Text style={styles.customerName}>
            {booking.customer?.name || `Customer #${booking.customer_id}`}
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
          ? "No visit fee yet"
          : `Visit fee: ${formatMoney(booking.visit_fee_amount)}`}
      </Text>
      {booking.current_refund_request ? (
        <Text style={styles.refundText}>
          Refund: {getRefundStatusLabel(booking.current_refund_request.status)}
        </Text>
      ) : null}

      <View style={styles.cardActions}>
        <SecondaryButton label="View details" onPress={() => onOpen(booking)} />
      </View>
    </Pressable>
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

function getBookingStatusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "Pending",
    quoted: "Quoted",
    awaiting_payment: "Awaiting payment",
    accepted: "In progress",
    rejected: "Declined",
    refunding: "Refund in progress",
    refunded: "Refunded",
    awaiting_confirmation: "Awaiting confirmation",
    completed: "Completed",
    cancelled: "Cancelled",
    visit_completed_closed: "Closed",
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

function getStatusBadgeStyle(status: string) {
  if (status === "pending") {
    return styles.statusWarning;
  }
  if (status === "quoted" || status === "awaiting_payment") {
    return styles.statusNeutral;
  }
  if (status === "accepted" || status === "completed") {
    return styles.statusSuccess;
  }
  if (status === "rejected" || status === "refunded") {
    return styles.statusMuted;
  }
  return styles.statusNeutral;
}

function filterActiveBookings(bookings: BookingDetail[]) {
  return bookings.filter(
    (booking) => !HIDDEN_ORDER_STATUSES.includes(String(booking.status)),
  );
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
  customerName: {
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
  proofBox: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.md,
  },
  proofText: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  proofFileList: {
    gap: spacing.xs,
  },
  proofFileText: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 18,
  },
  modalActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: spacing.sm,
  },
});
