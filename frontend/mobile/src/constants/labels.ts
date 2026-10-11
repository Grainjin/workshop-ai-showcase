
export const BOOKING_STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  quoted: "Quoted",
  awaiting_payment: "Awaiting payment",
  awaiting_visit_payment: "Visit fee due",
  visit_paid: "Visit fee paid",
  provider_arrived: "Provider arrived",
  awaiting_final_quote: "Final quote requested",
  final_quote_sent: "Final quote awaiting confirmation",
  awaiting_service_payment: "Service payment due",
  service_paid: "Service fee paid",
  accepted: "In progress",
  rejected: "Declined",
  refunding: "Refund in progress",
  refunded: "Refunded",
  partially_refunded: "Partially refunded",
  awaiting_confirmation: "Awaiting confirmation",
  completed: "Completed",
  cancelled: "Cancelled",
  visit_completed_closed: "Closed",
  cancelled_before_visit: "Closed",
  provider_no_show: "Closed",
  service_cancelled_after_payment: "Closed",
};

export const BOOKING_STATUS_LABELS_CHAT: Record<string, string> = {
  pending: "Pending review",
  quoted: "Quote awaiting confirmation",
  awaiting_payment: "Awaiting payment",
  awaiting_visit_payment: "Visit fee due",
  visit_paid: "Visit fee paid",
  provider_arrived: "Provider arrived",
  awaiting_final_quote: "Final quote requested",
  final_quote_sent: "Final quote awaiting confirmation",
  awaiting_service_payment: "Service payment due",
  service_paid: "Service fee paid",
  accepted: "In progress",
  rejected: "Declined",
  refunding: "Refund in progress",
  refunded: "Refunded",
  partially_refunded: "Partially refunded",
  awaiting_confirmation: "Awaiting confirmation",
  completed: "Completed",
  cancelled: "Cancelled",
  visit_completed_closed: "Closed",
  cancelled_before_visit: "Closed",
  provider_no_show: "Closed",
  service_cancelled_after_payment: "Closed",
};

export const REFUND_STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Declined",
  appealed: "Under review",
  admin_rejected: "Appeal declined",
  cancelled: "Cancelled",
};

export const PAYMENT_STATUS_LABELS: Record<string, string> = {
  pending: "Payment pending",
  checkout_created: "Checkout ready",
  processing: "Payment processing",
  authorized: "Payment authorized",
  paid: "Paid",
  voided: "Authorization released",
  failed: "Payment failed",
  capture_failed: "Payment capture failed",
  refund_failed: "Refund failed",
  refunded: "Refunded",
  partially_refunded: "Partially refunded",
};


export const WEEKDAY_LABELS: Array<{ value: number; label: string }> = [
  { value: 1, label: "Mon" },
  { value: 2, label: "Tue" },
  { value: 3, label: "Wed" },
  { value: 4, label: "Thu" },
  { value: 5, label: "Fri" },
  { value: 6, label: "Sat" },
  { value: 7, label: "Sun" },
];

export function getBookingStatusLabel(status: string) {
  return BOOKING_STATUS_LABELS[status] ?? status;
}

export function getBookingStatusLabelForChat(status: string) {
  return BOOKING_STATUS_LABELS_CHAT[status] ?? status;
}

export function getRefundStatusLabel(status: string) {
  return REFUND_STATUS_LABELS[status] ?? status;
}

export function getPaymentStatusLabel(status: string) {
  return PAYMENT_STATUS_LABELS[status] ?? status;
}


export function getWeekdayLabel(weekday: number) {
  return WEEKDAY_LABELS.find((item) => item.value === weekday)?.label ?? `Day ${weekday}`;
}
