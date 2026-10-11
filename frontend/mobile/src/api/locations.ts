import { apiClient } from "./client";
import type { ApiResponse } from "../types/auth";
import type { ServiceLocation } from "../types/location";

type ServiceLocationList = {
  items: ServiceLocation[];
};

export async function getServiceLocations(parentId?: number) {
  const response = await apiClient.get<ApiResponse<ServiceLocationList>>(
    "/locations",
    {
      params: {
        parent_id: parentId,
      },
    },
  );

  const items = response.data.data?.items;
  if (!Array.isArray(items)) {
    throw new Error("Service areas returned an invalid response.");
  }

  return items;
}

export async function getServiceLocation(locationId: number) {
  const response = await apiClient.get<ApiResponse<ServiceLocation>>(
    `/locations/${locationId}`,
  );

  return response.data.data;
}

export async function getServiceLocationPath(locationId: number) {
  const selected = await getServiceLocation(locationId);
  if (!selected) {
    throw new Error("The saved service area was not found.");
  }

  if (selected.level === "province") {
    return { province: selected, city: null, district: null };
  }

  if (!selected.parent_id) throw new Error("The saved service area has no parent.");

  if (selected.level === "city") {
    const province = await getServiceLocation(selected.parent_id);
    if (!province || province.level !== "province") {
      throw new Error("The saved city has no province.");
    }
    return { province, city: selected, district: null };
  }

  const district = selected;

  const city = await getServiceLocation(district.parent_id!);
  if (!city || city.level !== "city" || !city.parent_id) {
    throw new Error("The saved district has no city.");
  }

  const province = await getServiceLocation(city.parent_id);
  if (!province || province.level !== "province") {
    throw new Error("The saved city has no province.");
  }

  return { province, city, district };
}
