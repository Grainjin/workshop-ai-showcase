import { apiClient } from "./client";
import type { ApiResponse } from "../types/auth";
import type {
  AIActionCancelResult,
  AIActionExecutionResult,
  AIChatHistoryPage,
  AIChatRequest,
  AIChatResponse,
} from "../types/ai";

const AI_REQUEST_TIMEOUT_MS = 300000;

export async function sendAIChatMessage(payload: AIChatRequest) {
  const response = await apiClient.post<ApiResponse<AIChatResponse>>(
    "/ai/chat/sync",
    payload,
    {
      timeout: AI_REQUEST_TIMEOUT_MS,
    },
  );

  return response.data.data;
}

export async function getAIChatMessages(page = 1, pageSize = 50) {
  const response = await apiClient.get<ApiResponse<AIChatHistoryPage>>(
    "/ai/chat/messages",
    {
      params: {
        page,
        page_size: pageSize,
      },
    },
  );

  return response.data.data;
}

export async function clearAIChatMessages() {
  const response = await apiClient.delete<ApiResponse<{ deleted_count: number }>>(
    "/ai/chat/messages",
  );

  return response.data.data;
}

export async function confirmAIAction(actionId: number) {
  const response = await apiClient.post<ApiResponse<AIActionExecutionResult>>(
    "/ai/actions/confirm",
    {
      action_id: actionId,
    },
    {
      timeout: AI_REQUEST_TIMEOUT_MS,
    },
  );

  return response.data.data;
}

export async function cancelAIAction(actionId: number) {
  const response = await apiClient.put<ApiResponse<AIActionCancelResult>>(
    `/ai/actions/${actionId}/cancel`,
  );

  return response.data.data;
}
