export type SubmerchantType =
  | "PERSONAL"
  | "PRIVATE_COMPANY"
  | "LIMITED_OR_JOINT_STOCK_COMPANY";

export type SubmerchantStatus =
  | "draft"
  | "active"
  | "rejected"
  | "update_failed"
  | string;

export type ProviderSubmerchant = {
  id: number;
  provider_profile_id: number;
  submerchant_type: SubmerchantType;
  submerchant_external_id: string;
  name: string;
  email: string;
  gsm_number: string;
  address: string;
  iban: string;
  contact_name: string | null;
  contact_surname: string | null;
  identity_number: string | null;
  tax_office: string | null;
  tax_number: string | null;
  legal_company_title: string | null;
  currency: string;
  status: SubmerchantStatus;
  iyzico_error_code: string | null;
  iyzico_error_message: string | null;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProviderSubmerchantPayload = {
  submerchant_type: SubmerchantType;
  name: string;
  email: string;
  gsm_number: string;
  address: string;
  iban: string;
  contact_name: string | null;
  contact_surname: string | null;
  identity_number: string | null;
  tax_office: string | null;
  tax_number: string | null;
  legal_company_title: string | null;
  currency: "TRY";
};

export type AdminSubmerchant = ProviderSubmerchant;
