import type { BookingDetail, PaymentSummary } from "../types/booking";
import { getPaymentAction } from "./payment";

export const CUSTOMER_CANCELLABLE_BOOKING_STATUSES = [
  "pending",
  "quoted",
  "awaiting_payment",
  "awaiting_visit_payment",
] as const;

export const CUSTOMER_REFUNDABLE_BOOKING_STATUSES = [
  "provider_arrived",
  "awaiting_final_quote",
  "final_quote_sent",
  "awaiting_service_payment",
  "service_paid",
  "awaiting_confirmation",
  "completed",
] as const;

export const CUSTOMER_POST_VISIT_CANCELLABLE_BOOKING_STATUSES = [
  "visit_paid",
  "provider_arrived",
  "awaiting_final_quote",
  "final_quote_sent",
  "awaiting_service_payment",
  "service_paid",
  "accepted",
] as const;

const CHAT_HIDDEN_BOOKING_STATUSES = new Set([
  "completed",
  "cancelled",
  "refunded",
  "partially_refunded",
  "visit_completed_closed",
]);

const BLOCKING_REFUND_REQUEST_STATUSES = new Set([
  "pending",
  "rejected",
  "appealed",
  "approved",
]);

export function canCustomerCancelBooking(status?: string | null) {
  return CUSTOMER_CANCELLABLE_BOOKING_STATUSES.includes(
    status as (typeof CUSTOMER_CANCELLABLE_BOOKING_STATUSES)[number],
  );
}

export function canCustomerCancelAfterVisit(
  status?: string | null,
  payment?: Pick<PaymentSummary, "status"> | null,
) {
  void payment;
  return CUSTOMER_POST_VISIT_CANCELLABLE_BOOKING_STATUSES.includes(
    status as (typeof CUSTOMER_POST_VISIT_CANCELLABLE_BOOKING_STATUSES)[number],
  );
}

export function canCustomerRequestRefund(
  booking: Pick<BookingDetail, "status" | "current_refund_request">,
  payment?: Pick<PaymentSummary, "status"> | null,
) {
  return (
    CUSTOMER_REFUNDABLE_BOOKING_STATUSES.includes(
      booking.status as (typeof CUSTOMER_REFUNDABLE_BOOKING_STATUSES)[number],
    ) &&
    payment?.status === "paid" &&
    !(
      booking.current_refund_request &&
      BLOCKING_REFUND_REQUEST_STATUSES.has(booking.current_refund_request.status)
    )
  );
}

export function shouldShowBookingInChat(status?: string | null) {
  return !CHAT_HIDDEN_BOOKING_STATUSES.has(String(status ?? ""));
}

export function isFinalQuoteStage(booking: Pick<BookingDetail, "status">) {
  return ["awaiting_final_quote", "final_quote_sent"].includes(
    String(booking.status),
  );
}

export function shouldShowInitialQuote(booking: Pick<BookingDetail, "status">) {
  return !isFinalQuoteStage(booking);
}

export function shouldShowFinalQuote(
  booking: Pick<BookingDetail, "status" | "final_quote_declined_at">,
) {
  return !(
    booking.status === "awaiting_final_quote" &&
    Boolean(booking.final_quote_declined_at)
  );
}

export function shouldShowInitialQuoteHistory(
  booking: Pick<BookingDetail, "status">,
) {
  return !isFinalQuoteStage(booking);
}

export type CustomerBookingListAction =
  | "accept_quote"
  | "accept_final_quote"
  | "pay"
  | "confirm_complete";

export function getCustomerBookingListAction(
  booking: { status?: string | null },
  payment?: Pick<PaymentSummary, "status"> | null,
): CustomerBookingListAction | null {
  if (booking.status === "quoted") {
    return "accept_quote";
  }
  if (booking.status === "final_quote_sent") {
    return "accept_final_quote";
  }
  if (booking.status === "awaiting_confirmation") {
    return "confirm_complete";
  }

  const paymentAction = getPaymentAction(
    String(booking.status ?? ""),
    payment as PaymentSummary | null,
  );
  return paymentAction === "pay" || paymentAction === "continue" ? "pay" : null;
}
