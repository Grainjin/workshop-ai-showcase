import { Platform } from "react-native";

import { apiClient } from "./client";
import type { ApiResponse } from "../types/auth";
import type {
  CustomerProfile,
  CustomerProfilePatchPayload,
  CustomerProfilePayload,
  CustomerProfileUpdateResponse,
} from "../types/customer";
import type {
  BookingCreateResponseData,
  PaymentHistoryEntry,
  BookingActionResponseData,
  BookingDetail,
  BookingPayload,
  BookingUpdateResponseData,
} from "../types/booking";
import type { ChatRoom } from "../types/chat";
import type { PaginatedData } from "../types/chat";
import type { ProviderPortfolio } from "../types/provider";
import type { Review } from "../types/review";
import type { ProviderSearchQueryParams } from "../features/provider-search/search-filter-state";
import type {
  AddFavoriteProviderResponse,
  CustomerHomeRecommendations,
  CustomerProviderDetail,
  CustomerProviderSearchResults,
  FavoriteProvider,
  RemoveFavoriteProviderResponse,
} from "../types/provider";

export async function getCustomerProfile() {
  const response =
    await apiClient.get<ApiResponse<CustomerProfile>>("/customer/profile");

  return response.data.data;
}

export async function updateCustomerServiceProvince(
  serviceProvince: string,
  serviceLocationId: number,
) {
  const response = await apiClient.put<ApiResponse<CustomerProfileUpdateResponse>>(
    "/customer/profile/service-province",
    {
      service_province: serviceProvince,
      service_location_id: serviceLocationId,
    },
  );

  return response.data.data;
}

export async function updateCustomerProfile(payload: CustomerProfilePayload) {
  const response = await apiClient.put<ApiResponse<CustomerProfileUpdateResponse>>(
    "/customer/profile",
    payload,
  );

  return response.data.data;
}

export async function patchCustomerProfile(payload: CustomerProfilePatchPayload) {
  const response = await apiClient.patch<ApiResponse<CustomerProfileUpdateResponse>>(
    "/customer/profile",
    payload,
  );

  return response.data.data;
}

export async function getCustomerHomeRecommendations(
  serviceProvince: string,
  providerTag?: string,
  serviceLocationId?: number,
) {
  const response = await apiClient.get<ApiResponse<CustomerHomeRecommendations>>(
    "/customer/home/recommendations",
    {
      params: {
        service_province: serviceProvince,
        service_location_id: serviceLocationId,
        provider_tag: providerTag || undefined,
      },
    },
  );

  return response.data.data;
}

export async function getCustomerProviderDetail(providerId: number) {
  const response = await apiClient.get<ApiResponse<CustomerProviderDetail>>(
    `/customer/providers/${providerId}`,
  );

  return response.data.data;
}

export async function getCustomerFavourites(page = 1, pageSize = 20) {
  const response = await apiClient.get<
    ApiResponse<PaginatedData<FavoriteProvider>>
  >("/customer/favorites", {
    params: {
      page,
      page_size: pageSize,
    },
  });

  return response.data.data;
}

export async function addCustomerFavourite(providerProfileId: number) {
  const response = await apiClient.post<ApiResponse<AddFavoriteProviderResponse>>(
    `/customer/favorites/${providerProfileId}`,
  );

  return response.data.data;
}

export async function removeCustomerFavourite(providerProfileId: number) {
  const response = await apiClient.delete<
    ApiResponse<RemoveFavoriteProviderResponse>
  >(`/customer/favorites/${providerProfileId}`);

  return response.data.data;
}

export async function openChatWithProvider(providerProfileId: number) {
  const response = await apiClient.post<
    ApiResponse<{
      message: string;
      chat_room: ChatRoom;
      chat_room_created: boolean;
    }>
  >(`/customer/chats/${providerProfileId}`);

  return response.data.data;
}

export async function createCustomerBooking(payload: BookingPayload) {
  const formData = new FormData();

  if (!payload.provider_profile_id) {
    throw new Error("provider_profile_id is required");
  }

  formData.append("provider_profile_id", String(payload.provider_profile_id));
  if (payload.chat_room_id) {
    formData.append("chat_room_id", String(payload.chat_room_id));
  }
  formData.append("title", payload.title);
  formData.append("service_category", payload.service_category);
  formData.append("service_description", payload.service_description);
  formData.append("service_address", payload.service_address);
  formData.append("service_latitude", String(payload.service_latitude));
  formData.append("service_longitude", String(payload.service_longitude));
  if (payload.customer_current_address) {
    formData.append("customer_current_address", payload.customer_current_address);
  }
  if (payload.customer_current_latitude != null) {
    formData.append(
      "customer_current_latitude",
      String(payload.customer_current_latitude),
    );
  }
  if (payload.customer_current_longitude != null) {
    formData.append(
      "customer_current_longitude",
      String(payload.customer_current_longitude),
    );
  }
  formData.append("scheduled_start_time", payload.scheduled_start_time);
  formData.append("scheduled_end_time", payload.scheduled_end_time);

  for (const attachment of payload.attachments ?? []) {
    if (Platform.OS === "web") {
      const fileResponse = await fetch(attachment.uri);
      const blob = await fileResponse.blob();
      formData.append(
        "attachments",
        new File([blob], attachment.fileName, {
          type: attachment.mimeType || blob.type || "application/octet-stream",
        }),
      );
    } else {
      formData.append("attachments", {
        uri: attachment.uri,
        name: attachment.fileName,
        type: attachment.mimeType,
      } as unknown as Blob);
    }
  }

  const response = await apiClient.post<ApiResponse<BookingCreateResponseData>>(
    "/bookings",
    formData,
  );

  return response.data.data;
}

export async function getCustomerBookings(status?: string, page = 1, pageSize = 20) {
  const response = await apiClient.get<ApiResponse<PaginatedData<BookingDetail>>>(
    "/customer/bookings",
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

export async function updateCustomerPendingBooking(
  bookingId: number,
  payload: BookingPayload,
) {
  const response = await apiClient.put<ApiResponse<BookingUpdateResponseData>>(
    `/customer/bookings/${bookingId}`,
    {
      title: payload.title,
      service_description: payload.service_description,
      service_address: payload.service_address,
      service_latitude: payload.service_latitude,
      service_longitude: payload.service_longitude,
      customer_current_address: payload.customer_current_address ?? null,
      customer_current_latitude: payload.customer_current_latitude ?? null,
      customer_current_longitude: payload.customer_current_longitude ?? null,
      scheduled_start_time: payload.scheduled_start_time,
      scheduled_end_time: payload.scheduled_end_time,
    },
  );

  return response.data.data;
}

export async function acceptCustomerBookingQuote(bookingId: number) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/accept-quote`,
  );

  return response.data.data;
}

export async function rejectCustomerBookingQuote(
  bookingId: number,
  statusNote: string,
) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/reject-quote`,
    {
      status_note: statusNote,
    },
  );

  return response.data.data;
}

export async function cancelCustomerBooking(bookingId: number) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/cancel`,
  );

  return response.data.data;
}

export async function payCustomerBooking(
  bookingId: number,
  paymentMethod = "iyzico_checkout",
  idempotencyKey?: string,
  paymentStage: "visit_fee" | "service_fee" = "visit_fee",
) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/pay`,
    {
      payment_method: paymentMethod,
      payment_stage: paymentStage,
    },
    idempotencyKey
      ? {
          headers: {
            "Idempotency-Key": idempotencyKey,
          },
        }
      : undefined,
  );

  return response.data.data;
}

export async function cancelCustomerBookingAfterVisit(
  bookingId: number,
  statusNote = "Customer cancelled after provider arrival without requesting a refund.",
) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/close-final-quote`,
    { status_note: statusNote },
  );

  return response.data.data;
}

export async function acceptCustomerFinalQuote(bookingId: number) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/accept-final-quote`,
  );
  return response.data.data;
}

export async function rejectCustomerFinalQuote(bookingId: number, statusNote: string) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/reject-final-quote`,
    { status_note: statusNote },
  );
  return response.data.data;
}

export async function requestCustomerRefund(
  bookingId: number,
  reason: string,
  refundAmount?: number,
) {
  const response = await apiClient.post<ApiResponse<BookingActionResponseData>>(
    `/bookings/${bookingId}/refund-requests`,
    {
      reason,
      ...(refundAmount != null ? { refund_amount: refundAmount } : {}),
    },
    {
      timeout: 30000,
    },
  );

  return response.data.data;
}

export async function cancelCustomerRefund(refundRequestId: number) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/refund-requests/${refundRequestId}/cancel`,
    undefined,
    {
      timeout: 30000,
    },
  );

  return response.data.data;
}

export async function appealCustomerRefund(
  refundRequestId: number,
  appealReason: string,
) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/refund-requests/${refundRequestId}/appeal`,
    {
      appeal_reason: appealReason,
    },
    {
      timeout: 30000,
    },
  );

  return response.data.data;
}

export async function confirmCustomerBookingComplete(bookingId: number) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/confirm-complete`,
  );

  return response.data.data;
}

export async function createCustomerReview(
  bookingId: number,
  rating: number,
  comment: string,
) {
  const response = await apiClient.post<ApiResponse<{ review: Review }>>(
    `/bookings/${bookingId}/review`,
    {
      rating,
      comment,
    },
  );

  return response.data.data;
}

export async function rejectCustomerBookingComplete(
  bookingId: number,
  statusNote: string,
) {
  const response = await apiClient.put<ApiResponse<BookingActionResponseData>>(
    `/customer/bookings/${bookingId}/reject-complete`,
    {
      status_note: statusNote,
    },
  );

  return response.data.data;
}

export async function getPublicProviderPortfolios(
  providerId: number,
  page = 1,
  pageSize = 4,
) {
  const response = await apiClient.get<ApiResponse<PaginatedData<ProviderPortfolio>>>(
    `/providers/${providerId}/portfolio`,
    {
      params: {
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function getPublicProviderPortfolioItem(
  providerId: number,
  portfolioId: number,
) {
  const response = await apiClient.get<ApiResponse<ProviderPortfolio>>(
    `/providers/${providerId}/portfolio/${portfolioId}`,
  );

  return response.data.data;
}

export async function getPublicProviderReviews(
  providerId: number,
  page = 1,
  pageSize = 10,
) {
  const response = await apiClient.get<ApiResponse<PaginatedData<Review>>>(
    `/providers/${providerId}/reviews`,
    {
      params: {
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function searchCustomerProviders(
  keyword: string,
  serviceProvince: string,
  serviceLocationId?: number,
  filters: ProviderSearchQueryParams = {},
) {
  const response = await apiClient.get<ApiResponse<CustomerProviderSearchResults>>(
    "/customer/providers/search",
    {
      params: {
        keyword,
        service_province: serviceProvince,
        service_location_id: serviceLocationId,
        ...filters,
      },
    },
  );

  return response.data.data;
}

/** History only — the demo has no stored card methods to manage. */
export async function getCustomerPayments(page = 1, pageSize = 20) {
  const response = await apiClient.get<
    ApiResponse<PaginatedData<PaymentHistoryEntry>>
  >("/customer/payments", {
    params: {
      page,
      page_size: pageSize,
    },
  });

  return response.data.data;
}
