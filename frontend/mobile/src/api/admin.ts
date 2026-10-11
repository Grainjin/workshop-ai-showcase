import { apiClient } from "./client";
import type { ApiResponse } from "../types/auth";
import type { PaymentHistoryEntry, RefundRequestSummary } from "../types/booking";
import type { PaginatedData } from "../types/chat";
import type { AdminSubmerchant } from "../types/marketplace";
import type {
  IdentityVerificationApplication,
  ProviderPortfolio,
  ProviderProfile,
  QualificationVerificationApplication,
} from "../types/provider";

export async function getAdminIdentityVerifications(status = "pending") {
  const response = await apiClient.get<ApiResponse<IdentityVerificationApplication[]>>(
    "/admin/identity-verifications",
    { params: { status } },
  );
  return response.data.data ?? [];
}

export async function decideAdminIdentityVerification(
  applicationId: number,
  status: "approved" | "rejected",
  reviewNote?: string,
) {
  const response = await apiClient.put<ApiResponse<IdentityVerificationApplication>>(
    `/admin/identity-verifications/${applicationId}/decision`,
    { status, review_note: reviewNote || null },
  );
  return response.data.data;
}

export async function getAdminQualificationVerifications(status = "pending") {
  const response = await apiClient.get<ApiResponse<QualificationVerificationApplication[]>>(
    "/admin/qualification-verifications",
    { params: { status } },
  );
  return response.data.data ?? [];
}

export async function decideAdminQualificationVerification(
  applicationId: number,
  status: "approved" | "rejected",
  reviewNote?: string,
) {
  const response = await apiClient.put<
    ApiResponse<{
      application: QualificationVerificationApplication;
      provider_profile_id: number | null;
    }>
  >(`/admin/qualification-verifications/${applicationId}/decision`, {
    status,
    review_note: reviewNote || null,
  });
  return response.data.data;
}

export async function downloadVerificationFile(fileUrl: string) {
  const response = await apiClient.get<Blob>(fileUrl, { responseType: "blob" });
  return response.data;
}

export async function getPendingProviderProfiles(page = 1, pageSize = 20) {
  const response = await apiClient.get<ApiResponse<PaginatedData<ProviderProfile>>>(
    "/admin/providers",
    {
      params: {
        verification_status: "pending",
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function getAdminProviderProfile(providerProfileId: number) {
  const response = await apiClient.get<ApiResponse<ProviderProfile>>(
    `/admin/providers/${providerProfileId}`,
  );

  return response.data.data;
}

export async function updateAdminProviderProfileVerification(
  providerProfileId: number,
  verificationStatus: "approved" | "rejected",
  verificationNote: string,
) {
  const response = await apiClient.put<
    ApiResponse<{
      message: string;
      profile: ProviderProfile;
    }>
  >(`/admin/providers/${providerProfileId}/verification`, {
    verification_status: verificationStatus,
    verification_note: verificationNote,
  });

  return response.data.data;
}

export async function getPendingProviderPortfolios(page = 1, pageSize = 20) {
  const response = await apiClient.get<ApiResponse<PaginatedData<ProviderPortfolio>>>(
    "/admin/provider-portfolios",
    {
      params: {
        verification_status: "pending",
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function getAdminProviderPortfolioItem(portfolioId: number) {
  const response = await apiClient.get<ApiResponse<ProviderPortfolio>>(
    `/admin/provider-portfolios/${portfolioId}`,
  );

  return response.data.data;
}

export async function updateAdminProviderPortfolioVerification(
  portfolioId: number,
  verificationStatus: "approved" | "rejected",
  verificationNote: string,
) {
  const response = await apiClient.put<
    ApiResponse<{
      message: string;
      portfolio: ProviderPortfolio;
    }>
  >(`/admin/provider-portfolios/${portfolioId}/verification`, {
    verification_status: verificationStatus,
    verification_note: verificationNote,
  });

  return response.data.data;
}

export async function getPendingRefundAppeals(page = 1, pageSize = 20) {
  const response = await apiClient.get<
    ApiResponse<PaginatedData<RefundRequestSummary>>
  >("/admin/refund-requests", {
    params: {
      status: "appealed",
      page,
      page_size: pageSize,
    },
  });

  return response.data.data;
}

export async function approveAdminRefundAppeal(
  refundRequestId: number,
  adminNote: string,
) {
  const response = await apiClient.put<
    ApiResponse<{
      message: string;
      refund_request: RefundRequestSummary;
    }>
  >(`/admin/refund-requests/${refundRequestId}/approve`, {
    admin_note: adminNote,
  });

  return response.data.data;
}

export async function rejectAdminRefundAppeal(
  refundRequestId: number,
  adminNote: string,
) {
  const response = await apiClient.put<
    ApiResponse<{
      message: string;
      refund_request: RefundRequestSummary;
    }>
  >(`/admin/refund-requests/${refundRequestId}/reject`, {
    admin_note: adminNote,
  });

  return response.data.data;
}

export async function getAdminSubmerchants(page = 1, pageSize = 20) {
  const response = await apiClient.get<
    ApiResponse<PaginatedData<AdminSubmerchant>>
  >("/admin/submerchants", {
    params: { page, page_size: pageSize },
  });
  return response.data.data;
}

export async function getAdminPayments(
  page = 1,
  pageSize = 20,
  filters?: {
    status?: string;
    settlementStatus?: string;
    providerProfileId?: number;
    bookingId?: number;
  },
) {
  const response = await apiClient.get<
    ApiResponse<PaginatedData<PaymentHistoryEntry>>
  >("/admin/payments", {
    params: {
      page,
      page_size: pageSize,
      status: filters?.status || undefined,
      settlement_status: filters?.settlementStatus || undefined,
      provider_profile_id: filters?.providerProfileId,
      booking_id: filters?.bookingId,
    },
  });
  return response.data.data;
}

export async function retryAdminSettlement(paymentId: number) {
  const response = await apiClient.post<
    ApiResponse<{ message: string; payment: PaymentHistoryEntry }>
  >(`/admin/payments/${paymentId}/settlement/retry`);
  return response.data.data;
}

export type LLMAuthMode = "key" | "chatgpt" | "grok";

export type LLMKeySource = "admin" | "env" | "none";

export type LLMOauthProviderStatus = {
  connected: boolean;
  pending: boolean;
  status: string;
  user_code?: string;
  url?: string;
  error?: string;
  note?: string;
};

export type LLMKeyStatus = {
  configured: boolean;
  source: LLMKeySource;
  provider: string;
  model: string;
  base_url: string;
  api_key_preview: string;
};

export type LLMProviderChoice = {
  id: string;
  label: string;
};

export type LLMOauthStatus = {
  auth: LLMAuthMode;
  saved_auth: LLMAuthMode;
  llm_provider: string;
  providers: LLMProviderChoice[];
  key: LLMKeyStatus;
  chatgpt: LLMOauthProviderStatus & { model?: string };
  grok: LLMOauthProviderStatus & { model?: string };
};

export type LLMModelList = {
  source: string;
  provider: string;
  models: string[];
  default: string;
};

export async function getLLMOauthStatus() {
  const response = await apiClient.get<ApiResponse<LLMOauthStatus>>("/ai/oauth");
  return response.data.data;
}

export async function startLLMOauth(provider: "chatgpt" | "grok") {
  const response = await apiClient.post<ApiResponse<LLMOauthStatus>>(
    `/ai/oauth/${provider}/start`,
  );
  return response.data.data;
}

export async function cancelLLMOauth(provider: "chatgpt" | "grok") {
  const response = await apiClient.post<ApiResponse<LLMOauthStatus>>(
    `/ai/oauth/${provider}/cancel`,
  );
  return response.data.data;
}

export async function logoutLLMOauth(provider: "chatgpt" | "grok") {
  const response = await apiClient.post<ApiResponse<LLMOauthStatus>>(
    `/ai/oauth/${provider}/logout`,
  );
  return response.data.data;
}

export async function setLLMOauthAuth(auth: LLMAuthMode, model = "") {
  const response = await apiClient.put<ApiResponse<LLMOauthStatus>>("/ai/oauth", {
    auth,
    model,
  });
  return response.data.data;
}

export async function listLLMModels(payload: {
  source?: "key" | "chatgpt" | "grok";
  provider?: string;
  api_key?: string;
  base_url?: string;
}) {
  const response = await apiClient.post<ApiResponse<LLMModelList>>(
    "/ai/oauth/models",
    payload,
  );
  return response.data.data;
}

export type LLMApiKeyUpdate = {
  provider: string;
  api_key: string;
  base_url?: string;
  model?: string;
};

export async function saveLLMApiKey(payload: LLMApiKeyUpdate) {
  const response = await apiClient.put<ApiResponse<LLMOauthStatus>>(
    "/ai/oauth/key",
    payload,
  );
  return response.data.data;
}

export async function clearLLMApiKey() {
  const response = await apiClient.delete<ApiResponse<LLMOauthStatus>>(
    "/ai/oauth/key",
  );
  return response.data.data;
}
