import { apiClient } from "./client";
import type { ApiResponse } from "../types/auth";
import type { PlaceDetails, PlaceSuggestion } from "../types/location";

/**
 * The app never talks to Google directly: the backend proxy holds the
 * key and the rate limit, and every platform uses these two calls.
 */
export async function searchPlaces(query: string, signal?: AbortSignal) {
  const response = await apiClient.get<
    ApiResponse<{ suggestions: PlaceSuggestion[] }>
  >("/places/autocomplete", {
    params: { q: query },
    signal,
  });

  return response.data.data?.suggestions ?? [];
}

export async function getPlaceDetails(placeId: string) {
  const response = await apiClient.get<ApiResponse<PlaceDetails>>(
    "/places/details",
    {
      params: { place_id: placeId },
    },
  );

  return response.data.data;
}
