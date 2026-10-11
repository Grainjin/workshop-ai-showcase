import type { User } from "./auth";
import type { ChatMessage, ChatRoom } from "./chat";
import type { ProviderProfile } from "./provider";

export type BookingStatus =
  | "pending"
  | "quoted"
  | "awaiting_payment"
  | "awaiting_visit_payment"
  | "visit_paid"
  | "provider_arrived"
  | "awaiting_final_quote"
  | "final_quote_sent"
  | "awaiting_service_payment"
  | "service_paid"
  | "accepted"
  | "rejected"
  | "refunding"
  | "refunded"
  | "partially_refunded"
  | "awaiting_confirmation"
  | "completed"
  | "cancelled"
  | "cancelled_before_visit"
  | "provider_no_show"
  | "visit_completed_closed"
  | "service_cancelled_after_payment"
  | string;

export type BookingDetail = {
  payment_method?: string | null;
  id: number;
  customer_id: number;
  provider_profile_id: number;
  chat_room_id: number | null;
  title: string;
  service_category: string | null;
  service_description: string;
  service_address: string;
  service_latitude: number;
  service_longitude: number;
  customer_current_address: string | null;
  customer_current_latitude: number | null;
  customer_current_longitude: number | null;
  booking_at: string;
  scheduled_start_time: string;
  scheduled_end_time: string;
  completed_at: string | null;
  total_amount: number;
  quote_amount: number | null;
  quote_message: string | null;
  expected_service_amount?: number | null;
  visit_fee_amount?: number | null;
  final_quote_amount?: number | null;
  final_quote_message?: string | null;
  arrival_started_at?: string | null;
  final_quote_declined_at?: string | null;
  final_quote_decline_reason?: string | null;
  final_quote_confirmed_at?: string | null;
  closed_reason?: string | null;
  quoted_at: string | null;
  status: BookingStatus;
  status_note: string | null;
  booking_notice?: string | null;
  customer?: User | null;
  provider?: ProviderProfile | null;
  attachments?: BookingAttachment[];
  current_refund_request?: RefundRequestSummary | null;
  last_declined_quote?: BookingQuoteRevision | null;
  last_declined_final_quote?: BookingQuoteRevision | null;
  current_quote_revision_id?: number | null;
  reference_price_range?: ReferencePriceRange;
};

export type ReferencePriceRange = {
  has_history: boolean;
  minimum: number | null;
  maximum: number | null;
  currency: "TRY" | string;
  sample_count: number;
};

export type BookingQuoteRevision = {
  revision_number: number;
  quote_amount: number;
  expected_service_amount?: number | null;
  visit_fee_amount?: number | null;
  total_amount?: number | null;
  quote_message?: string | null;
  declined_at?: string | null;
  decline_reason?: string | null;
};

export type BookingAttachmentPurpose =
  | "customer_attachment"
  | "quote_attachment"
  | "arrival_evidence"
  | "completion_proof";

export type BookingAttachment = {
  id: number;
  booking_id: number;
  uploaded_by_user_id: number;
  quote_revision_id?: number | null;
  purpose: BookingAttachmentPurpose;
  original_file_name: string;
  file_name: string;
  file_url: string;
  content_type: string;
  size: number;
  created_at: string;
};

export type RefundRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "appealed"
  | "admin_rejected"
  | "cancelled"
  | string;

export type PaymentStatus =
  | "pending"
  | "checkout_created"
  | "processing"
  | "authorized"
  | "paid"
  | "voided"
  | "failed"
  | "capture_failed"
  | "refund_failed"
  | "refunded"
  | "partially_refunded"
  | string;

export type PaymentStage = "visit_fee" | "service_fee";

export type RefundRequestSummary = {
  id: number;
  booking_id: number;
  payment_id: number;
  customer_id: number;
  provider_profile_id: number;
  reason: string;
  status: RefundRequestStatus;
  provider_note: string | null;
  appeal_reason: string | null;
  admin_note: string | null;
  previous_booking_status: string;
  created_at: string;
  responded_at: string | null;
  appealed_at: string | null;
  admin_responded_at: string | null;
  cancelled_at?: string | null;
  refunded_at?: string | null;
  refund_amount?: number | null;
  booking?: BookingDetail | null;
  payment?: PaymentSummary | null;
};

export type SettlementStatus =
  | "pending"
  | "approve_requested"
  | "approved"
  | "approval_failed"
  | "disapproved"
  | string;

export type PaymentSettlement = {
  id: number;
  payment_id: number;
  booking_id: number;
  provider_profile_id: number;
  platform_commission_rate: number;
  platform_commission_amount: number;
  provider_share_amount: number;
  payment_transaction_id: string | null;
  status: SettlementStatus;
  approve_requested_at: string | null;
  approved_at: string | null;
  failure_code: string | null;
  failure_message: string | null;
  retry_count: number;
  provider_payout_amount: number | null;
  merchant_payout_amount: number | null;
  provider_recovery_amount: number | null;
  recovery_status: string | null;
  iyzico_commission_rate_amount?: number | null;
  iyzico_commission_fee?: number | null;
  blockage_rate?: number | null;
  blockage_resolved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PaymentSummary = {
  id: number;
  booking_id: number;
  customer_id: number;
  provider_profile_id: number;
  amount: number;
  currency: string;
  status: PaymentStatus;
  payment_stage?: PaymentStage;
  payment_method: string | null;
  idempotency_key?: string | null;
  processing_started_at?: string | null;
  checkout_expires_at?: string | null;
  external_payment_id: string | null;
  conversation_id?: string | null;
  basket_id?: string | null;
  iyzico_token?: string | null;
  checkout_url?: string | null;
  iyzico_payment_id?: string | null;
  payment_transaction_id?: string | null;
  external_status?: string | null;
  failure_code?: string | null;
  failure_message?: string | null;
  created_at: string;
  paid_at: string | null;
  authorized_at?: string | null;
  voided_at?: string | null;
  capture_failed_at?: string | null;
  refunded_at: string | null;
  failed_at?: string | null;
  settlement?: PaymentSettlement | null;
};

/** What /customer/payments and /provider/payments return: a payment plus its booking. */
export type PaymentHistoryEntry = PaymentSummary & {
  booking?: BookingDetail | null;
};

export type BookingPayload = {
  provider_profile_id?: number;
  chat_room_id?: number | null;
  service_category: string;
  title: string;
  service_description: string;
  service_address: string;
  service_latitude: number;
  service_longitude: number;
  customer_current_address?: string | null;
  customer_current_latitude?: number | null;
  customer_current_longitude?: number | null;
  scheduled_start_time: string;
  scheduled_end_time: string;
  attachments?: BookingUploadFile[];
};

export type BookingUploadFile = {
  uri: string;
  fileName: string;
  mimeType: string;
  size?: number | null;
};

export type BookingCreateResponseData = {
  message?: string;
  booking: BookingDetail;
  chat_room: ChatRoom;
  chat_message: ChatMessage;
};

export type BookingUpdateResponseData = {
  message: string;
  booking: BookingDetail;
  chat_message: ChatMessage | null;
};

export type BookingActionResponseData = {
  message: string;
  booking: BookingDetail;
  chat_message?: ChatMessage | null;
  refund_request?: RefundRequestSummary | null;
  payment?: PaymentSummary | null;
  payment_page_url?: string | null;
  token?: string | null;
};
