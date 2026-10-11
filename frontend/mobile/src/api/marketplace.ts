import { apiClient } from "./client";
import type { ApiResponse } from "../types/auth";
import type {
  ProviderSubmerchant,
  ProviderSubmerchantPayload,
} from "../types/marketplace";

export async function getProviderSubmerchant() {
  const response = await apiClient.get<
    ApiResponse<{ submerchant: ProviderSubmerchant | null }>
  >("/provider/submerchant");
  return response.data.data?.submerchant ?? null;
}

export async function createProviderSubmerchant(
  payload: ProviderSubmerchantPayload,
) {
  const response = await apiClient.post<
    ApiResponse<{ submerchant: ProviderSubmerchant }>
  >("/provider/submerchant", payload);
  if (!response.data.data) {
    throw new Error("The server returned no payout account.");
  }
  return response.data.data.submerchant;
}

export async function updateProviderSubmerchant(
  payload: ProviderSubmerchantPayload,
) {
  const response = await apiClient.put<
    ApiResponse<{ submerchant: ProviderSubmerchant }>
  >("/provider/submerchant", payload);
  if (!response.data.data) {
    throw new Error("The server returned no payout account.");
  }
  return response.data.data.submerchant;
}
