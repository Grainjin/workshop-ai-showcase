import { apiClient } from "./client";
import type { ApiResponse } from "../types/auth";
import type { PaginatedData } from "../types/chat";
import type { Notification } from "../types/notification";

export async function getNotifications(page = 1, pageSize = 20) {
  const response = await apiClient.get<ApiResponse<PaginatedData<Notification>>>(
    "/notifications",
    {
      params: {
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function getNotificationSummary() {
  const response = await apiClient.get<
    ApiResponse<{
      unread_count: number;
      latest_notification: Notification | null;
    }>
  >("/notifications/summary");

  return response.data.data;
}

export async function markAllNotificationsAsRead() {
  const response = await apiClient.put<
    ApiResponse<{
      message: string;
      updated_count: number;
      unread_count: number;
    }>
  >("/notifications/read-all");

  return response.data.data;
}

export async function markNotificationAsRead(notificationId: number) {
  const response = await apiClient.put<
    ApiResponse<{
      message: string;
      unread_count: number;
      notification: Notification;
    }>
  >(`/notifications/${notificationId}/read`);

  return response.data.data;
}
