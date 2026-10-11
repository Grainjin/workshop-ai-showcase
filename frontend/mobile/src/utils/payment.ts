import type { BookingStatus, PaymentSummary } from "../types/booking";

export type PaymentAction = "pay" | "continue" | "processing" | null;

export function getDemoPaymentDisclosure(paymentMethod?: string | null) {
  return paymentMethod === "demo" ? "Demo payment — no real charge." : null;
}

export function createPaymentIdempotencyKey() {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi?.randomUUID) {
    return `payment-${cryptoApi.randomUUID()}`;
  }

  return `payment-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function shouldRotatePaymentIdempotencyKey(
  payment?: { status?: string | null; payment_method?: string | null } | null,
) {
  // Demo checkout completes inline, so release its key before the next fee stage.
  return payment?.status === "failed" ||
    (payment?.payment_method === "demo" && payment.status === "paid");
}

/** Keep the newest payment attempt when a booking has multiple attempts. */
export function indexLatestPayments(payments: PaymentSummary[]) {
  return payments.reduce<Record<number, PaymentSummary>>((indexed, payment) => {
    const existing = indexed[payment.booking_id];
    const paymentTime = new Date(payment.created_at).getTime();
    const existingTime = existing
      ? new Date(existing.created_at).getTime()
      : Number.NEGATIVE_INFINITY;

    if (
      !existing ||
      paymentTime > existingTime ||
      (paymentTime === existingTime && payment.id > existing.id)
    ) {
      indexed[payment.booking_id] = payment;
    }

    return indexed;
  }, {});
}

export function getPaymentAction(
  bookingStatus: BookingStatus | string,
  payment?: PaymentSummary | null,
): PaymentAction {
  if (!["awaiting_payment", "awaiting_visit_payment", "awaiting_service_payment"].includes(String(bookingStatus))) {
    return null;
  }

  if (payment?.status === "checkout_created") {
    return "continue";
  }

  if (payment?.status === "processing") {
    return "processing";
  }

  return "pay";
}

export function getPaymentStatusTone(status?: string | null) {
  if (status === "paid" || status === "authorized") {
    return "success" as const;
  }
  if (status === "failed" || status === "capture_failed" || status === "refund_failed") {
    return "danger" as const;
  }
  if (status === "refunded" || status === "partially_refunded" || status === "voided") {
    return "muted" as const;
  }
  return "warning" as const;
}
