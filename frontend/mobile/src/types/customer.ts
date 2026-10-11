export type CustomerProfile = {
  id: number;
  user_id: number;
  phone_number: string;
  address: string;
  service_province: string;
  service_location_id: number | null;
  latitude: number | null;
  longitude: number | null;
  current_address: string | null;
  current_latitude: number | null;
  current_longitude: number | null;
  default_service_address: string | null;
  default_service_latitude: number | null;
  default_service_longitude: number | null;
  notes: string | null;
};

export type CustomerProfileUpdateResponse = {
  message: string;
  profile: CustomerProfile;
};

export type CustomerProfilePayload = {
  phone_number: string;
  address: string;
  service_province: string;
  service_location_id: number | null;
  latitude: number | null;
  longitude: number | null;
  current_address: string | null;
  current_latitude: number | null;
  current_longitude: number | null;
  default_service_address: string | null;
  default_service_latitude: number | null;
  default_service_longitude: number | null;
  notes: string | null;
};

export type CustomerProfilePatchPayload = Partial<CustomerProfilePayload>;
