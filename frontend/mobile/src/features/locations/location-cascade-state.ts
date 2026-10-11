import type {
  ServiceAreaSelection,
  ServiceLocation,
} from "../../types/location";

export type LocationCascadeState = {
  province: ServiceLocation | null;
  city: ServiceLocation | null;
  district: ServiceLocation | null;
};

export const EMPTY_LOCATION_CASCADE: LocationCascadeState = {
  province: null,
  city: null,
  district: null,
};

export function chooseProvince(
  _current: LocationCascadeState,
  province: ServiceLocation,
): LocationCascadeState {
  return { province, city: null, district: null };
}

export function chooseCity(
  current: LocationCascadeState,
  city: ServiceLocation,
): LocationCascadeState {
  return { province: current.province, city, district: null };
}

export function chooseDistrict(
  current: LocationCascadeState,
  district: ServiceLocation,
): LocationCascadeState {
  return { ...current, district };
}

export function getCompletedLocation(
  current: LocationCascadeState,
  allowAnyLevel = false,
): ServiceAreaSelection | null {
  if (!current.province || (!allowAnyLevel && (!current.city || !current.district))) {
    return null;
  }

  const selected = current.district ?? current.city ?? current.province;
  const path = [current.province, current.city, current.district].filter(
    (item): item is ServiceLocation => Boolean(item),
  );

  return {
    serviceLocationId: selected.id,
    serviceProvince: current.province.name,
    label: path.map((item) => item.name).join(" / "),
  };
}
