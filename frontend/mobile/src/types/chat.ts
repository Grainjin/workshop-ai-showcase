import type { User } from "./auth";
import type { ProviderProfile } from "./provider";

export type PaginatedData<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type ChatMessageAttachment = {
  id: number;
  chat_room_id: number;
  chat_message_id: number | null;
  uploaded_by_user_id: number;
  original_file_name: string;
  file_name: string;
  file_url: string;
  content_type: string;
  size: number;
  created_at: string;
};

export type ChatMessage = {
  id: number;
  chat_room_id: number;
  sender_id: number;
  sender: User | null;
  message: string;
  message_type: string;
  related_type: string | null;
  related_id: number | null;
  metadata: Record<string, unknown> | null;
  attachments: ChatMessageAttachment[];
  created_at: string;
  read_at: string | null;
};

export type ChatRoom = {
  id: number;
  customer_id: number;
  provider_profile_id: number;
  created_at: string;
  last_message_at: string | null;
  customer: User | null;
  customer_online: boolean;
  provider: ProviderProfile | null;
  provider_online: boolean;
  last_message: ChatMessage | null;
  unread_count: number | null;
};

export type ChatMessageSendResponse = {
  chat_message: ChatMessage;
};
