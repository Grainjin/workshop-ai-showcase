/**
 * A location always comes from our /places APIs or from the device, so
 * the coordinates are never hand-typed. placeId is null for a device fix.
 */
export type SelectedLocation = {
  label: string;
  latitude: number;
  longitude: number;
  placeId: string | null;
};

export type PlaceSuggestion = {
  place_id: string;
  description: string;
};

export type PlaceDetails = {
  place_id: string;
  formatted_address: string;
  latitude: number;
  longitude: number;
};

export type ServiceLocationLevel = "province" | "city" | "district";

export type ServiceLocation = {
  id: number;
  parent_id: number | null;
  code: string;
  name: string;
  level: ServiceLocationLevel;
};

export type ServiceAreaSelection = {
  serviceLocationId: number;
  serviceProvince: string;
  label: string;
};
