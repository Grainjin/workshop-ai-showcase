import { apiClient } from "./client";
import { WS_BASE_URL } from "../config/env";
import type { ApiResponse } from "../types/auth";
import type { BookingDetail } from "../types/booking";
import type {
  ChatMessage,
  ChatMessageSendResponse,
  ChatRoom,
  PaginatedData,
} from "../types/chat";

export async function getCustomerChatRooms() {
  const response =
    await apiClient.get<ApiResponse<PaginatedData<ChatRoom>>>("/customer/chats");

  return response.data.data;
}

export async function getProviderChatRooms() {
  const response =
    await apiClient.get<ApiResponse<PaginatedData<ChatRoom>>>("/provider/chats");

  return response.data.data;
}

export async function getChatMessages(chatRoomId: number) {
  const response = await apiClient.get<ApiResponse<PaginatedData<ChatMessage>>>(
    `/chats/${chatRoomId}/messages`,
  );

  return response.data.data;
}

export async function getBookingById(bookingId: number) {
  const response = await apiClient.get<ApiResponse<BookingDetail>>(
    `/bookings/${bookingId}`,
  );

  return response.data.data;
}

export async function sendChatMessage(chatRoomId: number, message: string) {
  const response = await apiClient.post<ApiResponse<ChatMessageSendResponse>>(
    `/chats/${chatRoomId}/messages`,
    {
      message,
      attachment_ids: [],
    },
  );

  return response.data.data;
}

export function buildChatWebSocketUrl(chatRoomId: number) {
  return `${WS_BASE_URL}/ws/chats/${chatRoomId}`;
}

export function buildUserWebSocketUrl() {
  return `${WS_BASE_URL}/ws/me`;
}
