import * as ImagePicker from "expo-image-picker";
import { Modal, ScrollView, StyleSheet, Text, View } from "react-native";

import { BookingAttachments } from "./BookingAttachments";
import { BookingContextInformation } from "./BookingContextInformation";
import { BookingCoreDetails } from "./BookingCoreDetails";
import { BookingPriceBreakdown } from "./BookingPriceBreakdown";
import { MarketplaceBreakdownCard } from "./MarketplaceBreakdownCard";
import { PrimaryButton } from "./PrimaryButton";
import { QuoteAttachmentPicker } from "./QuoteAttachmentPicker";
import { ReferencePriceRange } from "./ReferencePriceRange";
import { SecondaryButton } from "./SecondaryButton";
import { TextField } from "./TextField";
import { DEMO_MODE } from "../config/env";
import { getBookingStatusLabel, getPaymentStatusLabel, getRefundStatusLabel } from "../constants/labels";
import { colors, radius, spacing } from "../theme/theme";
import type { BookingDetail, BookingUploadFile, PaymentSummary } from "../types/booking";
import { formatDateTime } from "../utils/datetime";
import { formatMoney } from "../utils/money";
import { shouldShowFinalQuote, shouldShowInitialQuote, shouldShowInitialQuoteHistory } from "../utils/bookingActions";

export type ProviderBookingDetailModalProps = {
  actionError?: string;
  booking: BookingDetail | null;
  finalQuoteAmount?: string;
  finalQuoteMessage?: string;
  includeLifecycleDates?: boolean;
  isActing?: boolean;
  onApproveRefund?: () => void;
  onClose: () => void;
  onComplete?: () => void;
  onPickCompletionProof?: () => void;
  onQuote?: () => void;
  onReject?: () => void;
  onRejectRefund?: () => void;
  onStartVisit?: () => void;
  onSubmitFinalQuote?: () => void;
  payment?: PaymentSummary | null;
  proofAssets?: ImagePicker.ImagePickerAsset[];
  quoteAmount?: string;
  quoteAmountError?: string;
  quoteMessage?: string;
  quoteFiles?: BookingUploadFile[];
  quoteFilesError?: string;
  setQuoteFiles?: (files: BookingUploadFile[]) => void;
  refundRejectReason?: string;
  rejectReason?: string;
  setFinalQuoteAmount?: (value: string) => void;
  setFinalQuoteMessage?: (value: string) => void;
  setQuoteAmount?: (value: string) => void;
  setQuoteMessage?: (value: string) => void;
  setRefundRejectReason?: (value: string) => void;
  setRejectReason?: (value: string) => void;
  setVisitFeeAmount?: (value: string) => void;
  showReadOnly?: boolean;
  visible?: boolean;
  visitFeeAmount?: string;
  visitFeeError?: string;
};

export function ProviderBookingDetailModal({
  actionError = "",
  booking,
  finalQuoteAmount = "",
  finalQuoteMessage = "",
  includeLifecycleDates = true,
  isActing = false,
  onApproveRefund,
  onClose,
  onComplete,
  onPickCompletionProof,
  onQuote,
  onReject,
  onRejectRefund,
  onStartVisit,
  onSubmitFinalQuote,
  payment,
  proofAssets = [],
  quoteAmount = "",
  quoteAmountError = "",
  quoteMessage = "",
  quoteFiles = [],
  quoteFilesError = "",
  setQuoteFiles = (_files: BookingUploadFile[]) => undefined,
  refundRejectReason = "",
  rejectReason = "",
  setFinalQuoteAmount = (_value: string) => undefined,
  setFinalQuoteMessage = (_value: string) => undefined,
  setQuoteAmount = (_value: string) => undefined,
  setQuoteMessage = (_value: string) => undefined,
  setRefundRejectReason = (_value: string) => undefined,
  setRejectReason = (_value: string) => undefined,
  setVisitFeeAmount = (_value: string) => undefined,
  showReadOnly = false,
  visible = true,
  visitFeeAmount = "",
  visitFeeError = "",
}: ProviderBookingDetailModalProps) {
  if (!booking || !visible) return null;

  const canRespond = !showReadOnly && booking.status === "pending" && Boolean(onQuote || onReject);
  const canStartVisit = !showReadOnly && booking.status === "visit_paid" && Boolean(onStartVisit);
  const canSubmitFinalQuote = !showReadOnly && ["provider_arrived", "awaiting_final_quote"].includes(String(booking.status)) && Boolean(onSubmitFinalQuote);
  const canComplete = !showReadOnly && ["service_paid", "accepted"].includes(String(booking.status)) && Boolean(onComplete);
  const canProcessRefund = !showReadOnly && booking.status === "refunding" && booking.current_refund_request?.status === "pending" && Boolean(onApproveRefund || onRejectRefund);
  const hasAnyAction = canRespond || canStartVisit || canSubmitFinalQuote || canComplete || canProcessRefund;

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent visible>
      <View style={styles.modalOverlay}>
        <View style={styles.modalCard}>
          <Text style={styles.modalTitle}>Booking #{booking.id}</Text>
          <ScrollView contentContainerStyle={styles.content}>
            <View style={styles.detailBox}>
              <DetailRow label="Status" value={getBookingStatusLabel(booking.status)} />
              {booking.booking_notice ? <DetailRow label="Notice" value={booking.booking_notice} /> : null}
              {payment ? <DetailRow label="Payment status" value={getPaymentStatusLabel(payment.status)} /> : null}
              {payment?.failure_message ? <DetailRow label="Payment note" value={payment.failure_message} /> : null}
              <BookingCoreDetails booking={booking} includeLifecycleDates={includeLifecycleDates} role="provider" />
              <BookingAttachments booking={booking} />
              <BookingPriceBreakdown booking={booking} showFinalQuote={shouldShowFinalQuote(booking)} showInitialQuote={shouldShowInitialQuote(booking)} showPreviousDeclined={shouldShowInitialQuoteHistory(booking)} />
              <BookingContextInformation booking={booking} />
              {payment && shouldShowFinalQuote(booking) ? (
                <MarketplaceBreakdownCard
                  amount={(booking.final_quote_amount ?? 0) + (booking.visit_fee_amount ?? 0)}
                  estimateOnly
                  payment={payment}
                  serviceAmount={booking.final_quote_amount}
                  serviceAmountLabel="Service amount"
                  title="Current payment breakdown"
                  visitFeeAmount={booking.visit_fee_amount}
                />
              ) : null}
              {booking.current_refund_request ? <RefundDetails booking={booking} /> : null}
            </View>

            {canRespond ? (
              <>
                <ReferencePriceRange audience="provider" range={booking.reference_price_range} />
                <TextField error={quoteAmountError} keyboardType="decimal-pad" label="Expected service amount" onChangeText={setQuoteAmount} placeholder="Expected work amount" value={quoteAmount} />
                <TextField error={visitFeeError} keyboardType="decimal-pad" label="Visit fee" onChangeText={setVisitFeeAmount} placeholder="Amount paid before the visit" value={visitFeeAmount} />
                <MarketplaceBreakdownCard amount={Number(quoteAmount) + Number(visitFeeAmount)} serviceAmount={quoteAmount} title="Provider income estimate" visitFeeAmount={visitFeeAmount} />
                <TextField label="Quote notes" multiline numberOfLines={2} onChangeText={setQuoteMessage} placeholder="Optional notes" value={quoteMessage} />
                <QuoteAttachmentPicker disabled={isActing} error={quoteFilesError} files={quoteFiles} onChange={setQuoteFiles} />
              </>
            ) : null}

            {canStartVisit ? (DEMO_MODE ? <DemoProofNotice /> : <ProofPicker assets={proofAssets} isActing={isActing} label="Arrival evidence" onPick={onPickCompletionProof} />) : null}

            {canSubmitFinalQuote ? (
              <>
                <ReferencePriceRange audience="provider" range={booking.reference_price_range} />
                <TextField keyboardType="decimal-pad" label="Final quote amount" onChangeText={setFinalQuoteAmount} placeholder="Enter the final amount" value={finalQuoteAmount} />
                <MarketplaceBreakdownCard
                  amount={finalQuoteAmount.trim() ? Number(finalQuoteAmount) + Number(booking.visit_fee_amount ?? 0) : null}
                  serviceAmount={finalQuoteAmount.trim() ? finalQuoteAmount : null}
                  serviceAmountLabel="Service amount"
                  title="Final quote estimate"
                  visitFeeAmount={finalQuoteAmount.trim() ? booking.visit_fee_amount : null}
                />
                <TextField label="Final quote message" multiline numberOfLines={2} onChangeText={setFinalQuoteMessage} placeholder="Explain the final amount if it changed" value={finalQuoteMessage} />
                <QuoteAttachmentPicker disabled={isActing} error={quoteFilesError} files={quoteFiles} onChange={setQuoteFiles} />
              </>
            ) : null}

            {canComplete ? (DEMO_MODE ? <DemoProofNotice /> : <ProofPicker assets={proofAssets} isActing={isActing} label="Completion proof" onPick={onPickCompletionProof} />) : null}
            {actionError ? <Text style={styles.error}>{actionError}</Text> : null}
            {!hasAnyAction ? <Text style={styles.noAction}>No actions available for this booking status.</Text> : null}
          </ScrollView>

          <View style={styles.actions}>
            <SecondaryButton disabled={isActing} label="Close" onPress={onClose} />
            {canRespond ? <SecondaryButton disabled={isActing} label="Decline booking" onPress={onReject!} /> : null}
            {canProcessRefund ? <SecondaryButton disabled={isActing} label="Reject refund" onPress={onRejectRefund!} /> : null}
            {canRespond ? <PrimaryButton disabled={isActing} isLoading={isActing} label="Send quote" onPress={onQuote!} /> : null}
            {canStartVisit ? <PrimaryButton disabled={isActing} isLoading={isActing} label={DEMO_MODE ? "Start visit with demo proof" : "Start visit"} onPress={onStartVisit!} /> : null}
            {canSubmitFinalQuote ? <PrimaryButton disabled={isActing} isLoading={isActing} label="Send final quote" onPress={onSubmitFinalQuote!} /> : null}
            {canComplete ? <PrimaryButton disabled={isActing} isLoading={isActing} label={DEMO_MODE ? "Complete with demo proof" : "Mark complete"} onPress={onComplete!} /> : null}
            {canProcessRefund ? <PrimaryButton disabled={isActing} isLoading={isActing} label="Approve refund" onPress={onApproveRefund!} /> : null}
          </View>
        </View>
      </View>
    </Modal>
  );
}

function RefundDetails({ booking }: { booking: BookingDetail }) {
  const request = booking.current_refund_request;
  if (!request) return null;
  return (
    <>
      <DetailRow label="Refund status" value={getRefundStatusLabel(request.status)} />
      <DetailRow label="Refund amount" value={request.refund_amount == null ? "Full paid amount" : formatMoney(request.refund_amount)} />
      <DetailRow label="Refund reason" value={request.reason} />
      <DetailRow label="Rejection note" value={request.provider_note || "—"} />
      <DetailRow label="Appeal reason" value={request.appeal_reason || "—"} />
      <DetailRow label="Support response" value={request.admin_note || "—"} />
    </>
  );
}

function DemoProofNotice() {
  return <Text style={styles.proofText}>This action records server-selected simulated proof. No real service or uploaded evidence.</Text>;
}

function ProofPicker({ assets, isActing, label, onPick }: { assets: ImagePicker.ImagePickerAsset[]; isActing: boolean; label: string; onPick?: () => void }) {
  return (
    <View style={styles.proofBox}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.proofText}>{assets.length > 0 ? `Selected ${assets.length} files` : `Add photos or video for ${label.toLowerCase()}`}</Text>
      {assets.length > 0 ? <View style={styles.fileList}>{assets.map((asset, index) => <Text key={`${asset.uri}-${index}`} style={styles.fileText}>{asset.fileName || `${label} ${index + 1}`}</Text>)}</View> : null}
      <SecondaryButton disabled={isActing || !onPick} label="Add proof" onPress={onPick || (() => undefined)} />
    </View>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return <View style={styles.row}><Text style={styles.detailLabel}>{label}</Text><Text style={styles.detailValue}>{value}</Text></View>;
}

const styles = StyleSheet.create({
  modalOverlay: { backgroundColor: "rgba(0,0,0,0.28)", flex: 1, justifyContent: "flex-end" },
  modalCard: { backgroundColor: colors.background, borderTopLeftRadius: radius.md, borderTopRightRadius: radius.md, gap: spacing.md, maxHeight: "88%", padding: spacing.lg },
  modalTitle: { color: colors.text, fontSize: 21, fontWeight: "800", marginBottom: spacing.md },
  content: { gap: spacing.md, paddingBottom: spacing.md },
  detailBox: { backgroundColor: colors.surface, borderRadius: 12, gap: spacing.sm, padding: spacing.md },
  row: { gap: spacing.xs },
  detailLabel: { color: colors.mutedText, fontSize: 13, fontWeight: "700" },
  detailValue: { color: colors.text, fontSize: 15, lineHeight: 21 },
  proofBox: { backgroundColor: colors.surface, borderRadius: 12, gap: spacing.sm, padding: spacing.md },
  proofText: { color: colors.mutedText, fontSize: 13 },
  fileList: { gap: spacing.xs },
  fileText: { color: colors.text, fontSize: 13 },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, justifyContent: "flex-end", paddingTop: spacing.md },
  error: { color: colors.danger, fontSize: 14 },
  noAction: { color: colors.mutedText, fontSize: 14, textAlign: "center" },
});
