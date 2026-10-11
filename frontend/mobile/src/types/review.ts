import type { User } from "./auth";

export type Review = {
  id: number;
  booking_id: number;
  customer_id: number;
  provider_profile_id: number;
  rating: number;
  comment: string | null;
  created_at: string | null;
  is_visible: boolean;
  embedding_status: string | null;
  embedding_error: string | null;
  embedding_synced_at: string | null;
  customer?: User | null;
};
