import type { PaginatedData } from "./chat";

export type AIChatRequest = {
  message: string;
  service_province?: string | null;
  service_address?: string | null;
  max_price?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  max_distance_km?: number | null;
  scheduled_start_time?: string | null;
  scheduled_end_time?: string | null;
  candidate_provider_ids?: number[];
};

export type AIChatHistoryMessage = {
  id: number;
  user_id: number;
  role: "user" | "assistant" | string;
  message: string;
  intent: string | null;
  response_type: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

export type AIProviderRecommendation = {
  provider_id: number;
  business_name: string;
  service_province: string | null;
  tags: string | string[];
  hourly_rate: number | null;
  distance_km?: number | null;
  match_score?: number | null;
  matched_tags?: string[];
  reason?: string;
  stats?: {
    average_rating?: number | null;
    review_count?: number | null;
    completed_bookings?: number | null;
  };
};

export type AIConfirmationField = {
  label?: string | null;
  value?: unknown;
};

export type AIConfirmationCard = {
  ui_type?: string;
  action_id: number;
  action_type: string;
  title: string;
  description?: string | null;
  status: string;
  expires_at?: string | null;
  fields?: AIConfirmationField[];
  provider?: Record<string, unknown> | null;
  booking_id?: number | null;
  refund_request_id?: number | null;
  warnings?: string[];
  warning?: string | null;
  confirm_label?: string;
  cancel_label?: string;
};

export type AIBookingDraft = {
  draft_status: string;
  draft_type?: string;
  missing_field_names?: string[];
  missing_fields?: Array<{
    name: string;
    label: string;
    type: string;
    question: string;
  }>;
  provider_choices?: Record<string, unknown>[];
  preview?: Record<string, unknown> | null;
  next_question?: string | null;
};

export type AIChatResponse = AIChatRequest & {
  type: string;
  answer: string;
  recommendation_count?: number | null;
  recommendations?: AIProviderRecommendation[] | null;
  review_context_source?: string | null;
  chat_room?: Record<string, unknown> | null;
  booking?: Record<string, unknown> | null;
  pending_action?: Record<string, unknown> | null;
  confirmation_card?: AIConfirmationCard | null;
  booking_draft?: AIBookingDraft | null;
  next_question?: string | null;
  tool_error?: Record<string, unknown> | null;
};

export type AIChatHistoryPage = PaginatedData<AIChatHistoryMessage>;

export type AIActionExecutionResult = {
  action_id: number;
  action_type: string;
  executed: boolean;
  pending_action: Record<string, unknown>;
  result: Record<string, unknown>;
};

export type AIActionCancelResult = {
  action_id: number;
  cancelled: boolean;
  pending_action: Record<string, unknown>;
};
