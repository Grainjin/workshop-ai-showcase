import { Modal, ScrollView, StyleSheet, Text, View } from "react-native";

import { BookingContextInformation } from "./BookingContextInformation";
import { BookingCoreDetails } from "./BookingCoreDetails";
import { BookingPriceBreakdown } from "./BookingPriceBreakdown";
import { BookingAttachments } from "./BookingAttachments";
import { DateTimeField } from "./DateTimeField";
import type { BookingRequestFormState } from "./BookingRequestModal";
import { PrimaryButton } from "./PrimaryButton";
import { ReferencePriceRange } from "./ReferencePriceRange";
import { SecondaryButton } from "./SecondaryButton";
import { TextField } from "./TextField";
import { getBookingStatusLabel, getPaymentStatusLabel, getRefundStatusLabel } from "../constants/labels";
import { colors, radius, spacing } from "../theme/theme";
import type { BookingDetail, PaymentSummary } from "../types/booking";
import { formatDateTime } from "../utils/datetime";
import { formatMoney, formatPayLabel } from "../utils/money";
import {
  canCustomerCancelBooking,
  canCustomerCancelAfterVisit,
  canCustomerRequestRefund,
  shouldShowFinalQuote,
  shouldShowInitialQuote,
  shouldShowInitialQuoteHistory,
} from "../utils/bookingActions";
import { getPaymentAction } from "../utils/payment";
import { shouldShowCustomerReferencePrice } from "../utils/referencePrice";

export type CustomerBookingDetailModalProps = {
  actionError?: string;
  booking: BookingDetail | null;
  bookingForm?: BookingRequestFormState | null;
  includeLifecycleDates?: boolean;
  isActing?: boolean;
  onAcceptFinalQuote?: () => void;
  onAcceptQuote?: () => void;
  onAppealRefund?: () => void;
  onCancel?: () => void;
  onCancelAfterVisit?: () => void;
  onCancelRefund?: () => void;
  onClose: () => void;
  onConfirmComplete?: () => void;
  onOpenProvider?: (booking: BookingDetail) => void;
  onPay?: () => void;
  onRejectFinalQuote?: () => void;
  onRejectQuote?: () => void;
  onRequestRefund?: () => void;
  onUpdate?: () => void;
  payment?: PaymentSummary | null;
  refundAmount?: string;
  refundAppealReason?: string;
  refundReason?: string;
  setBookingForm?: (value: BookingRequestFormState | null) => void;
  setRefundAmount?: (value: string) => void;
  setRefundAppealReason?: (value: string) => void;
  setRefundReason?: (value: string) => void;
  showInlineRefundFields?: boolean;
  visible?: boolean;
};

export function CustomerBookingDetailModal({
  actionError = "",
  booking,
  bookingForm,
  includeLifecycleDates = true,
  isActing = false,
  onAcceptFinalQuote,
  onAcceptQuote,
  onAppealRefund,
  onCancel,
  onCancelAfterVisit,
  onCancelRefund,
  onClose,
  onConfirmComplete,
  onOpenProvider,
  onPay,
  onRejectFinalQuote,
  onRejectQuote,
  onRequestRefund,
  onUpdate,
  payment,
  refundAmount = "",
  refundAppealReason = "",
  refundReason = "",
  setBookingForm,
  setRefundAmount = (_value: string) => undefined,
  setRefundAppealReason = (_value: string) => undefined,
  setRefundReason = (_value: string) => undefined,
  showInlineRefundFields = false,
  visible = true,
}: CustomerBookingDetailModalProps) {
  if (!booking || !visible) {
    return null;
  }

  const paymentAction = getPaymentAction(booking.status, payment);
  const canEdit = booking.status === "pending" && Boolean(bookingForm && onUpdate);
  const canReviewQuote = booking.status === "quoted" && Boolean(onAcceptQuote || onRejectQuote);
  const canReviewFinalQuote = booking.status === "final_quote_sent" && Boolean(onAcceptFinalQuote || onRejectFinalQuote);
  const canPay = Boolean(onPay) && (paymentAction === "pay" || paymentAction === "continue");
  const canCancel = Boolean(onCancel) && canCustomerCancelBooking(booking.status);
  const canCancelAfterVisit =
    Boolean(onCancelAfterVisit) &&
    canCustomerCancelAfterVisit(booking.status, payment);
  const canRequestRefund = Boolean(onRequestRefund) && canCustomerRequestRefund(booking, payment);
  const canConfirmComplete = Boolean(onConfirmComplete) && booking.status === "awaiting_confirmation";
  const canCancelRefund = Boolean(onCancelRefund) && booking.status === "refunding" && ["pending", "rejected"].includes(String(booking.current_refund_request?.status || ""));
  const canAppealRefund = Boolean(onAppealRefund) && booking.status === "refunding" && booking.current_refund_request?.status === "rejected";
  const hasAnyAction = canEdit || canReviewQuote || canReviewFinalQuote || canPay || canCancel || canCancelAfterVisit || canRequestRefund || canConfirmComplete || canCancelRefund || canAppealRefund;

  function updateFormField(field: keyof BookingRequestFormState, value: string) {
    if (!bookingForm || !setBookingForm) return;
    setBookingForm({ ...bookingForm, [field]: value });
  }

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Booking #{booking.id}</Text>
          <ScrollView contentContainerStyle={styles.content}>
            <View style={styles.detailBox}>
              <DetailRow label="Status" value={getBookingStatusLabel(booking.status)} />
              {booking.booking_notice ? <DetailRow label="Notice" value={booking.booking_notice} /> : null}
              <DetailRow label="Payment status" value={payment ? getPaymentStatusLabel(payment.status) : "Not started"} />
              {payment?.failure_message ? <DetailRow label="Payment note" value={payment.failure_message} /> : null}
              <BookingCoreDetails booking={booking} includeLifecycleDates={includeLifecycleDates} onOpenProvider={onOpenProvider} role="customer" />
              <BookingAttachments booking={booking} />
              <BookingPriceBreakdown booking={booking} showFinalQuote={shouldShowFinalQuote(booking)} showInitialQuote={shouldShowInitialQuote(booking)} showPreviousDeclined={shouldShowInitialQuoteHistory(booking)} />
              {shouldShowCustomerReferencePrice(booking) ? (
                <ReferencePriceRange audience="customer" range={booking.reference_price_range} />
              ) : null}
              <BookingContextInformation booking={booking} />
              {booking.current_refund_request ? <RefundDetails booking={booking} payment={payment} /> : null}
            </View>

            {canEdit && bookingForm ? (
              <>
                <TextField label="Booking title" onChangeText={(value) => updateFormField("title", value)} value={bookingForm.title} />
                <TextField label="Service description" multiline numberOfLines={3} onChangeText={(value) => updateFormField("serviceDescription", value)} value={bookingForm.serviceDescription} />
                <TextField label="Service address" onChangeText={(value) => updateFormField("serviceAddress", value)} value={bookingForm.serviceAddress} />
                <DateTimeField label="Start time" onChange={(value) => updateFormField("scheduledStartTime", value)} value={bookingForm.scheduledStartTime} />
                <DateTimeField label="End time" onChange={(value) => updateFormField("scheduledEndTime", value)} value={bookingForm.scheduledEndTime} />
              </>
            ) : null}

            {canReviewFinalQuote ? <Text style={styles.hint}>Review the final quote above before confirming it.</Text> : null}
            {canPay ? (
              <Text style={styles.hint}>
                {paymentAction === "continue"
                  ? "Your checkout is ready. Continue payment to complete this step."
                  : `Pay ${formatMoney(booking.status === "awaiting_service_payment" ? booking.final_quote_amount ?? booking.quote_amount : booking.visit_fee_amount ?? booking.quote_amount)} to continue.`}
              </Text>
            ) : null}

            {showInlineRefundFields && canRequestRefund ? (
              <>
                <TextField keyboardType="decimal-pad" label="Refund amount (optional)" onChangeText={setRefundAmount} placeholder="Leave blank for full refund" value={refundAmount} />
                <TextField label="Refund reason" multiline numberOfLines={3} onChangeText={setRefundReason} placeholder="Reason for refund" value={refundReason} />
              </>
            ) : null}
            {canAppealRefund ? <TextField label="Appeal reason" multiline numberOfLines={3} onChangeText={setRefundAppealReason} placeholder="Reason for appeal" value={refundAppealReason} /> : null}
            {!hasAnyAction ? <Text style={styles.noAction}>No actions available for this booking status.</Text> : null}
            {actionError ? <Text style={styles.error}>{actionError}</Text> : null}
          </ScrollView>

          <View style={styles.actions}>
            <SecondaryButton disabled={isActing} label="Close" onPress={onClose} />
            {canCancel || canCancelAfterVisit ? (
              <SecondaryButton
                disabled={isActing}
                label="Cancel"
                onPress={canCancel ? onCancel! : onCancelAfterVisit!}
              />
            ) : null}
            {canReviewQuote ? <SecondaryButton disabled={isActing} label="Decline quote" onPress={onRejectQuote!} /> : null}
            {canReviewFinalQuote ? <SecondaryButton disabled={isActing} label="Decline final quote" onPress={onRejectFinalQuote!} /> : null}
            {canRequestRefund ? <SecondaryButton disabled={isActing} label="Request refund" onPress={onRequestRefund!} /> : null}
            {canCancelRefund ? <SecondaryButton disabled={isActing} label="Cancel refund" onPress={onCancelRefund!} /> : null}
            {canEdit ? <PrimaryButton disabled={isActing} isLoading={isActing} label="Save changes" onPress={onUpdate!} /> : null}
            {canReviewQuote ? <PrimaryButton disabled={isActing} isLoading={isActing} label="Accept quote" onPress={onAcceptQuote!} /> : null}
            {canReviewFinalQuote ? <PrimaryButton disabled={isActing} isLoading={isActing} label="Accept final quote" onPress={onAcceptFinalQuote!} /> : null}
            {canPay ? <PrimaryButton disabled={isActing} isLoading={isActing} label={paymentAction === "continue" ? "Continue payment" : formatPayLabel(booking.status === "awaiting_service_payment" ? booking.final_quote_amount ?? booking.quote_amount : booking.visit_fee_amount ?? booking.quote_amount)} onPress={onPay!} /> : null}
            {canConfirmComplete ? <PrimaryButton disabled={isActing} isLoading={isActing} label="Confirm complete" onPress={onConfirmComplete!} /> : null}
            {canAppealRefund ? <PrimaryButton disabled={isActing} isLoading={isActing} label="Submit appeal" onPress={onAppealRefund!} /> : null}
          </View>
        </View>
      </View>
    </Modal>
  );
}

function RefundDetails({ booking, payment }: { booking: BookingDetail; payment?: PaymentSummary | null }) {
  const request = booking.current_refund_request;
  if (!request) return null;
  return (
    <>
      <DetailRow label="Refund status" value={getRefundStatusLabel(request.status)} />
      <DetailRow label="Original payment" value={payment ? formatMoney(payment.amount) : "—"} />
      <DetailRow label="Refund amount" value={request.refund_amount == null ? "Full paid amount" : formatMoney(request.refund_amount)} />
      <DetailRow label="Refund reason" value={request.reason} />
      <DetailRow label="Provider response" value={request.provider_note || "—"} />
      <DetailRow label="Appeal reason" value={request.appeal_reason || "—"} />
      <DetailRow label="Support response" value={request.admin_note || "—"} />
      <DetailRow label="Requested at" value={formatDateTime(request.created_at)} />
      <DetailRow label="Provider responded at" value={formatDateTime(request.responded_at)} />
      <DetailRow label="Appealed at" value={formatDateTime(request.appealed_at)} />
      <DetailRow label="Support responded at" value={formatDateTime(request.admin_responded_at)} />
      <DetailRow label="Refunded at" value={formatDateTime(request.refunded_at)} />
      {request.status === "approved" ? <Text style={styles.refundNotice}>Refunds usually appear in the customer account within 14 business days.</Text> : null}
    </>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return <View style={styles.row}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{value}</Text></View>;
}

const styles = StyleSheet.create({
  modalOverlay: { backgroundColor: "rgba(0,0,0,0.28)", flex: 1, justifyContent: "flex-end" },
  modalCard: { backgroundColor: colors.background, borderTopLeftRadius: radius.md, borderTopRightRadius: radius.md, gap: spacing.md, maxHeight: "88%", padding: spacing.lg },
  modalTitle: { color: colors.text, fontSize: 21, fontWeight: "800", marginBottom: spacing.md },
  content: { gap: spacing.md, paddingBottom: spacing.md },
  detailBox: { backgroundColor: colors.surface, borderRadius: 12, gap: spacing.sm, padding: spacing.md },
  row: { gap: spacing.xs },
  label: { color: colors.mutedText, fontSize: 13, fontWeight: "700" },
  value: { color: colors.text, fontSize: 15, lineHeight: 21 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, justifyContent: "flex-end", paddingTop: spacing.md },
  hint: { color: colors.mutedText, fontSize: 13, lineHeight: 19 },
  noAction: { color: colors.mutedText, fontSize: 14, textAlign: "center" },
  error: { color: colors.danger, fontSize: 14 },
  refundNotice: { color: colors.mutedText, fontSize: 13, lineHeight: 19, marginTop: spacing.sm },
});
