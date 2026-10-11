import { Platform } from "react-native";

import { apiClient } from "./client";
import { DEMO_MODE } from "../config/env";
import type { ApiResponse } from "../types/auth";
import type {
  BookingActionResponseData,
  BookingDetail,
  BookingUploadFile,
  PaymentHistoryEntry,
} from "../types/booking";
import { buildBookingQuoteBody } from "../utils/bookingQuoteUpload";
import type { PaginatedData } from "../types/chat";
import type {
  ProviderAvailability,
  ProviderAvailabilityOverride,
  ProviderAvailabilityResponseData,
  ProviderAvailabilityUpdateResponseData,
  ApprovedServices,
  IdentityVerificationApplication,
  ProviderOperatingSettingsPayload,
  ProviderServiceArea,
  ProviderVerificationStatus,
  QualificationVerificationApplication,
  QualificationVerificationPayload,
  VerificationUploadFile,
  ProviderContactProfilePatchPayload,
  ProviderContactProfilePayload,
  ProviderContactProfileUpdateResponse,
  ProviderPortfolio,
  ProviderProfileMutationResponse,
  ProviderProfilePayload,
  ProviderProfile,
} from "../types/provider";
import type { Review } from "../types/review";

export type LocalVerificationFile = {
  uri: string;
  fileName?: string | null;
  mimeType?: string | null;
};

async function appendUploadFile(
  formData: FormData,
  field: string,
  file: LocalVerificationFile,
) {
  const fileName = file.fileName || "verification-file";
  const mimeType = file.mimeType || "application/octet-stream";
  if (Platform.OS === "web") {
    const fileResponse = await fetch(file.uri);
    const blob = await fileResponse.blob();
    formData.append(field, new File([blob], fileName, { type: mimeType || blob.type }));
  } else {
    formData.append(field, {
      uri: file.uri,
      name: fileName,
      type: mimeType,
    } as unknown as Blob);
  }
}

export async function getProviderVerificationStatus() {
  const response = await apiClient.get<ApiResponse<ProviderVerificationStatus>>(
    "/provider/verification-status",
  );
  return response.data.data;
}

export async function getIdentityVerification() {
  const response = await apiClient.get<ApiResponse<IdentityVerificationApplication>>(
    "/provider/identity-verification",
  );
  return response.data.data;
}

export async function submitIdentityVerification(payload: {
  dateOfBirth: string;
  documentType: "national_id" | "passport";
  files: LocalVerificationFile[];
}) {
  const formData = new FormData();
  formData.append("date_of_birth", payload.dateOfBirth);
  formData.append("document_type", payload.documentType);
  for (const file of payload.files) await appendUploadFile(formData, "files", file);
  const response = await apiClient.post<ApiResponse<IdentityVerificationApplication>>(
    "/provider/identity-verification",
    formData,
    { timeout: 120000 },
  );
  return response.data.data;
}

export async function getQualificationVerification() {
  const response = await apiClient.get<ApiResponse<QualificationVerificationApplication>>(
    "/provider/qualification-verification",
  );
  return response.data.data;
}

export async function uploadQualificationFiles(files: LocalVerificationFile[]) {
  const formData = new FormData();
  for (const file of files) await appendUploadFile(formData, "files", file);
  const response = await apiClient.post<ApiResponse<{ files: VerificationUploadFile[] }>>(
    "/provider/qualification-files/upload",
    formData,
    { timeout: 120000 },
  );
  return response.data.data;
}

export async function submitQualificationVerification(
  payload: QualificationVerificationPayload,
) {
  const response = await apiClient.post<ApiResponse<QualificationVerificationApplication>>(
    "/provider/qualification-verification",
    payload,
  );
  return response.data.data;
}

export async function getApprovedServices() {
  const response = await apiClient.get<ApiResponse<ApprovedServices>>(
    "/provider/approved-services",
  );
  return response.data.data;
}

export async function updateProviderOperatingSettings(
  payload: ProviderOperatingSettingsPayload,
) {
  const response = await apiClient.patch<ApiResponse<{ message: string }>>(
    "/provider/operating-settings",
    payload,
  );
  return response.data.data;
}

export async function getProviderServiceAreas() {
  const response = await apiClient.get<ApiResponse<{ service_areas: ProviderServiceArea[] }>>(
    "/provider/service-areas",
  );
  return response.data.data;
}

export async function updateProviderServiceAreas(serviceLocationIds: number[]) {
  const response = await apiClient.put<ApiResponse<{ service_areas: ProviderServiceArea[] }>>(
    "/provider/service-areas",
    { service_location_ids: serviceLocationIds },
  );
  return response.data.data;
}

export async function getProviderProfile() {
  const response =
    await apiClient.get<ApiResponse<ProviderProfile>>("/provider/profile");

  return response.data.data;
}

export async function createProviderProfile(payload: ProviderProfilePayload) {
  const response = await apiClient.post<
    ApiResponse<ProviderProfileMutationResponse>
  >("/provider/profile", payload);

  return response.data.data;
}

export async function updateProviderProfile(payload: ProviderProfilePayload) {
  const response = await apiClient.put<
    ApiResponse<ProviderProfileMutationResponse>
  >("/provider/profile", payload);

  return response.data.data;
}

export async function uploadProviderCertificates(
  files: Array<{
    uri: string;
    fileName?: string | null;
    mimeType?: string | null;
  }>,
) {
  const formData = new FormData();

  for (const file of files) {
    const fileName = file.fileName || "certificate.jpg";
    const mimeType = file.mimeType || "application/octet-stream";

    if (Platform.OS === "web") {
      const fileResponse = await fetch(file.uri);
      const blob = await fileResponse.blob();
      const uploadFile = new File([blob], fileName, {
        type: mimeType || blob.type || "application/octet-stream",
      });
      formData.append("files", uploadFile);
    } else {
      formData.append("files", {
        uri: file.uri,
        name: fileName,
        type: mimeType,
      } as unknown as Blob);
    }
  }

  const response = await apiClient.post<
    ApiResponse<{
      files: Array<{
        original_file_name: string;
        file_name: string;
        file_url: string;
        content_type: string;
        media_type: "image" | "video" | "document" | string;
        size: number;
      }>;
    }>
  >("/provider/certificates/upload", formData, {
    timeout: 120000,
  });

  return response.data.data;
}

export async function updateProviderContactProfile(
  payload: ProviderContactProfilePayload,
) {
  const response = await apiClient.put<
    ApiResponse<ProviderContactProfileUpdateResponse>
  >("/provider/profile/contact", payload);

  return response.data.data;
}

export async function patchProviderContactProfile(
  payload: ProviderContactProfilePatchPayload,
) {
  const response = await apiClient.patch<
    ApiResponse<ProviderContactProfileUpdateResponse>
  >("/provider/profile/contact", payload);

  return response.data.data;
}

export async function getProviderAvailability() {
  const response = await apiClient.get<ApiResponse<ProviderAvailabilityResponseData>>(
    "/provider/availability",
  );

  return response.data.data;
}

export async function updateProviderAvailability(
  availabilities: Array<
    Pick<ProviderAvailability, "weekday" | "start_time" | "end_time" | "is_available">
  >,
) {
  const response =
    await apiClient.put<ApiResponse<ProviderAvailabilityUpdateResponseData>>(
      "/provider/availability",
      {
        availabilities,
      },
    );

  return response.data.data;
}

export async function getProviderAvailabilityOverrides(month: string) {
  const response = await apiClient.get<
    ApiResponse<ProviderAvailabilityOverride[]>
  >("/provider/availability/overrides", {
    params: {
      month,
    },
  });

  return response.data.data;
}

export async function updateProviderAvailabilityOverride(
  overrideDate: string,
  payload: {
    start_time: string | null;
    end_time: string | null;
    is_available: boolean;
  },
) {
  const response = await apiClient.put<ApiResponse<ProviderAvailabilityOverride>>(
    `/provider/availability/overrides/${overrideDate}`,
    payload,
  );

  return response.data.data;
}

export async function deleteProviderAvailabilityOverride(overrideDate: string) {
  const response = await apiClient.delete<ApiResponse<{ message: string }>>(
    `/provider/availability/overrides/${overrideDate}`,
  );

  return response.data.data;
}

export async function getProviderPortfolios(page = 1, pageSize = 20) {
  const response = await apiClient.get<ApiResponse<PaginatedData<ProviderPortfolio>>>(
    "/provider/portfolio",
    {
      params: {
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function getProviderPortfolioItem(portfolioId: number) {
  const response = await apiClient.get<ApiResponse<ProviderPortfolio>>(
    `/provider/portfolio/${portfolioId}`,
  );

  return response.data.data;
}

export async function createProviderPortfolio(payload: {
  title: string;
  description?: string | null;
  mediaFiles: Array<{
    uri: string;
    fileName?: string | null;
    mimeType?: string | null;
  }>;
}) {
  const formData = new FormData();

  formData.append("title", payload.title);
  if (payload.description) {
    formData.append("description", payload.description);
  }

  for (const mediaFile of payload.mediaFiles) {
    const fileName = mediaFile.fileName || "portfolio.jpg";
    const mimeType = mediaFile.mimeType || "image/jpeg";

    if (Platform.OS === "web") {
      const fileResponse = await fetch(mediaFile.uri);
      const blob = await fileResponse.blob();
      const file = new File([blob], fileName, {
        type: mimeType || blob.type || "application/octet-stream",
      });

      formData.append("media_files", file);
    } else {
      formData.append("media_files", {
        uri: mediaFile.uri,
        name: fileName,
        type: mimeType,
      } as unknown as Blob);
    }
  }

  const response = await apiClient.post<ApiResponse<ProviderPortfolio>>(
    "/provider/portfolio",
    formData,
    {
      timeout: 120000,
    },
  );

  return response.data.data;
}

export async function getProviderReviews(page = 1, pageSize = 10) {
  const response = await apiClient.get<ApiResponse<PaginatedData<Review>>>(
    "/provider/reviews",
    {
      params: {
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function getProviderScheduleBookings(month: string) {
  const response = await apiClient.get<ApiResponse<BookingDetail[]>>(
    "/provider/bookings/schedule",
    {
      params: {
        month,
      },
    },
  );

  return response.data.data;
}

export async function getProviderBookings(status?: string, page = 1, pageSize = 50) {
  const response = await apiClient.get<ApiResponse<PaginatedData<BookingDetail>>>(
    "/provider/bookings",
    {
      params: {
        status: status || undefined,
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function quoteProviderBooking(
  bookingId: number,
  expectedServiceAmount: number,
  quoteMessage: string | null,
  visitFeeAmount: number,
  quoteFiles: BookingUploadFile[] = [],
) {
  const body = await buildBookingQuoteBody(
    {
      quote_amount: expectedServiceAmount,
      expected_service_amount: expectedServiceAmount,
      visit_fee_amount: visitFeeAmount,
      quote_message: quoteMessage,
    },
    quoteFiles,
    appendUploadFile,
  );
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/provider/bookings/${bookingId}/quote`,
    body,
    { timeout: 120000 },
  );

  return response.data.data;
}

export async function rejectProviderBooking(
  bookingId: number,
  statusNote: string,
) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/provider/bookings/${bookingId}/reject`,
    {
      status_note: statusNote,
    },
  );

  return response.data.data;
}

export async function completeProviderBooking(
  bookingId: number,
  proofFiles: Array<{
    uri: string;
    fileName?: string | null;
    mimeType?: string | null;
  }>,
  finalQuoteAmount?: number | null,
  finalQuoteMessage?: string | null,
) {
  if (DEMO_MODE) {
    const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
      `/provider/demo/bookings/${bookingId}/complete`,
    );
    return response.data.data;
  }
  const formData = new FormData();

  for (const proofFile of proofFiles) {
    const fileName = proofFile.fileName || "completion-proof.jpg";
    const mimeType = proofFile.mimeType || "image/jpeg";

    if (Platform.OS === "web") {
      const fileResponse = await fetch(proofFile.uri);
      const blob = await fileResponse.blob();
      const file = new File([blob], fileName, {
        type: mimeType || blob.type || "application/octet-stream",
      });

      formData.append("proof_files", file);
    } else {
      formData.append("proof_files", {
        uri: proofFile.uri,
        name: fileName,
        type: mimeType,
      } as unknown as Blob);
    }
  }

  if (finalQuoteAmount != null) {
    formData.append("final_quote_amount", String(finalQuoteAmount));
  }
  if (finalQuoteMessage?.trim()) {
    formData.append("final_quote_message", finalQuoteMessage.trim());
  }

  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/provider/bookings/${bookingId}/complete`,
    formData,
    {
      timeout: 120000,
    },
  );

  return response.data.data;
}

export async function startProviderVisit(
  bookingId: number,
  proofFiles: Array<{ uri: string; fileName?: string | null; mimeType?: string | null }>,
) {
  if (DEMO_MODE) {
    const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
      `/provider/demo/bookings/${bookingId}/start-visit`,
    );
    return response.data.data;
  }
  const formData = new FormData();
  for (const file of proofFiles) {
    await appendUploadFile(formData, "proof_files", file);
  }
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/provider/bookings/${bookingId}/start-visit`,
    formData,
    { timeout: 120000 },
  );
  return response.data.data;
}

export async function submitProviderFinalQuote(
  bookingId: number,
  amount: number,
  message?: string | null,
  quoteFiles: BookingUploadFile[] = [],
) {
  const body = await buildBookingQuoteBody(
    { quote_amount: amount, quote_message: message ?? null },
    quoteFiles,
    appendUploadFile,
  );
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/provider/bookings/${bookingId}/final-quote`,
    body,
    { timeout: 120000 },
  );
  return response.data.data;
}

export async function approveProviderRefundRequest(refundRequestId: number) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/provider/refund-requests/${refundRequestId}/approve`,
    undefined,
    {
      timeout: 30000,
    },
  );

  return response.data.data;
}

export async function rejectProviderRefundRequest(
  refundRequestId: number,
  providerNote: string,
) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/provider/refund-requests/${refundRequestId}/reject`,
    {
      provider_note: providerNote,
    },
    {
      timeout: 30000,
    },
  );

  return response.data.data;
}

/** The provider side of the same history: payouts they have received. */
export async function getProviderPayments(page = 1, pageSize = 20) {
  const response = await apiClient.get<
    ApiResponse<PaginatedData<PaymentHistoryEntry>>
  >("/provider/payments", {
    params: {
      page,
      page_size: pageSize,
    },
  });

  return response.data.data;
}
