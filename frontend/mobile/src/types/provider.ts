export type ProviderProfile = {
  id: number;
  user_id: number;
  business_name: string;
  bio: string;
  phone_number: string;
  address: string;
  service_province: string;
  service_location_id: number | null;
  latitude: number | null;
  longitude: number | null;
  business_place_id?: string | null;
  tags: string[];
  certificate_name: string;
  certificate_url: string;
  certificate_files: ProviderCertificateFile[];
  hourly_rate: number;
  verification_status: string;
  verification_note: string | null;
  /** Optional for legacy profiles; the verification helpers provide fallbacks. */
  entity_type?: string;
  identity_verification_status?: string;
  qualification_verification_status?: string;
  notes: string | null;
  is_online: boolean;
  is_open?: boolean;
  service_areas?: ProviderServiceArea[];
  average_rating?: number | null;
  review_count?: number;
  distance_km?: number | null;
};

export type ProviderCertificateFile = {
  id: number;
  provider_profile_id: number;
  file_url: string;
  original_file_name: string;
  content_type: string;
  media_type: "image" | "video" | "document" | string;
  sort_order: number;
  created_at: string;
};

export type ProviderContactProfilePayload = {
  phone_number: string;
  address: string;
  service_province: string;
  service_location_id: number | null;
  notes: string | null;
};

export type ProviderContactProfilePatchPayload =
  Partial<ProviderContactProfilePayload>;

export type ProviderContactProfileUpdateResponse = {
  message: string;
  profile: ProviderProfile;
};

export type ProviderProfilePayload = {
  business_name: string;
  bio: string;
  phone_number: string;
  address: string;
  service_province: string;
  service_location_id: number | null;
  latitude: number | null;
  longitude: number | null;
  tags: string[];
  certificate_name: string;
  certificate_url: string;
  certificate_files: Array<{
    file_url: string;
    original_file_name: string;
    content_type: string;
    media_type: string;
    sort_order: number;
  }>;
  hourly_rate: number;
  notes: string | null;
};

export type VerificationStatus =
  | "not_submitted"
  | "locked"
  | "pending"
  | "approved"
  | "rejected";

export type VerificationUploadFile = {
  id?: number;
  file_url: string;
  original_file_name: string;
  content_type: string;
  sort_order?: number;
  size?: number;
};

export type ProviderVerificationStatus = {
  identity_status: VerificationStatus;
  qualification_status: VerificationStatus;
  identity_application_id: number | null;
  qualification_application_id: number | null;
};

export type IdentityVerificationApplication = {
  id: number;
  user_id: number;
  submitted_first_name: string;
  submitted_last_name: string;
  date_of_birth: string;
  document_type: "national_id" | "passport";
  status: VerificationStatus;
  review_note: string | null;
  reviewed_by_user_id: number | null;
  submitted_at: string;
  reviewed_at: string | null;
  document_files: VerificationUploadFile[];
};

export type QualificationVerificationApplication = {
  id: number;
  user_id: number;
  entity_type: "personal" | "organisation";
  legal_name: string | null;
  unique_enterprise_id: string | null;
  display_name: string;
  description: string;
  contact_phone: string;
  business_address: string;
  business_place_id: string | null;
  business_latitude: number;
  business_longitude: number;
  service_categories: string[];
  service_location_ids: number[];
  service_areas: ProviderServiceArea[];
  status: VerificationStatus;
  review_note: string | null;
  reviewed_by_user_id: number | null;
  submitted_at: string;
  reviewed_at: string | null;
  qualification_files: VerificationUploadFile[];
};

export type QualificationVerificationPayload = {
  entity_type: "personal" | "organisation";
  legal_name: string | null;
  unique_enterprise_id: string | null;
  description: string;
  contact_phone: string;
  business_address: string;
  business_place_id: string | null;
  business_latitude: number;
  business_longitude: number;
  service_categories: string[];
  service_location_ids: number[];
  qualification_files: VerificationUploadFile[];
};

export type ApprovedServices = {
  approved_service_categories: string[];
  enabled_service_categories: string[];
};

export type ProviderOperatingSettingsPayload = {
  description?: string;
  contact_phone?: string;
  business_address?: string;
  business_place_id?: string | null;
  business_latitude?: number;
  business_longitude?: number;
  hourly_rate?: number;
  enabled_service_categories?: string[];
};

export type ProviderServiceArea = {
  id: number;
  name: string;
  level: "province" | "city" | "district";
  serviceProvince?: string;
  label?: string;
};

export type ProviderProfileMutationResponse = {
  message: string;
  profile: ProviderProfile;
};

export type ProviderAvailability = {
  id: number;
  provider_profile_id: number;
  weekday: number;
  start_time: string;
  end_time: string;
  is_available: boolean;
};

export type ProviderAvailabilityOverride = {
  id: number;
  provider_profile_id: number;
  override_date: string;
  start_time: string;
  end_time: string;
  is_available: boolean;
  created_at: string;
  updated_at: string;
};

export type ProviderAvailabilityResponseData = {
  availabilities: ProviderAvailability[];
};

export type ProviderAvailabilityUpdateResponseData = {
  message: string;
  availabilities: ProviderAvailability[];
};

export type ProviderPortfolioMedia = {
  id: number;
  portfolio_id: number;
  file_url: string;
  original_file_name: string | null;
  content_type: string | null;
  media_type: "image" | "video" | string;
  sort_order: number;
  created_at: string;
};

export type ProviderPortfolio = {
  id: number;
  provider_profile_id: number;
  title: string;
  description: string | null;
  image_url: string;
  original_file_name: string | null;
  content_type: string | null;
  media_type: "image" | "video" | string;
  media_items: ProviderPortfolioMedia[];
  verification_status: "pending" | "approved" | "rejected" | string;
  verification_note: string | null;
  created_at: string;
};

export type ProviderRecommendation = ProviderProfile & {
  avatar_url?: string | null;
  is_open?: boolean;
  first_portfolio_image_url: string | null;
  recommendation_score: number;
  matched_tags: string[];
  recommendation_reasons: string[];
};

export type CustomerHomeRecommendations = {
  service_province: string;
  service_location_id: number | null;
  history_provider_tag: string;
  items: ProviderRecommendation[];
};

export type CustomerProviderSearchResults = {
  keyword: string;
  tokens: string[];
  service_province: string;
  service_location_id: number | null;
  items: CustomerProviderSearchItem[];
};

export type CustomerProviderSearchItem = ProviderRecommendation & {
  avatar_url: string | null;
  distance_km: number | null;
  is_open: boolean;
};

export type CustomerProviderDetail = {
  provider: CustomerProviderDetailProfile;
  history: {
    id: number;
    customer_id: number;
    last_provider_profile_id: number | null;
    last_provider_tag: string;
    updated_at: string;
  };
};

export type CustomerProviderDetailProfile = ProviderProfile & {
  is_open: boolean;
  is_favorited: boolean;
  service_areas: ProviderServiceArea[];
};

export type FavoriteProvider = {
  id: number;
  customer_id: number;
  provider_profile_id: number;
  created_at: string;
  provider: ProviderProfile | null;
};

export type AddFavoriteProviderResponse = {
  message: string;
  favorite: FavoriteProvider;
};

export type RemoveFavoriteProviderResponse = {
  message: string;
};
