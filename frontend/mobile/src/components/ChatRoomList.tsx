import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useAuth } from "../context/AuthContext";
import { useRealtime } from "../context/RealtimeContext";
import { colors, radius, spacing } from "../theme/theme";
import type { RootStackParamList } from "../navigation/AppNavigator";
import type { ChatMessage, ChatRoom } from "../types/chat";

type ChatRoomListProps = {
  loadRooms: () => Promise<{ items: ChatRoom[] } | null>;
  viewerRole: "customer" | "provider";
};

export function ChatRoomList({ loadRooms, viewerRole }: ChatRoomListProps) {
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { user } = useAuth();
  const { subscribe } = useRealtime();
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [message, setMessage] = useState("");

  const refreshRooms = useCallback(
    async (options: { showLoading?: boolean } = {}) => {
      const { showLoading = true } = options;

      if (showLoading) {
        setIsLoading(true);
      }
      setMessage("");

      try {
        const data = await loadRooms();
        setRooms(data?.items ?? []);
      } catch {
        setRooms([]);
        setMessage("Couldn't load chats.");
      } finally {
        if (showLoading) {
          setIsLoading(false);
        }
      }
    },
    [loadRooms],
  );

  useFocusEffect(
    useCallback(() => {
      void refreshRooms();

      const unsubscribe = subscribe((data) => {
        const chatMessage = data?.chat_message;

        if (data?.type === "chat_message" && isIncomingChatMessage(chatMessage)) {
          const unreadCount =
            typeof data.unread_count === "number" ? data.unread_count : null;
          setRooms((currentRooms) => {
            const nextRooms = applyChatMessageToRooms(
              currentRooms,
              chatMessage,
              user?.id ?? null,
              unreadCount,
            );

            if (nextRooms === currentRooms) {
              void refreshRooms({ showLoading: false });
            }

            return nextRooms;
          });
          return;
        }

        if (
          (data?.type === "user_online" || data?.type === "user_offline") &&
          typeof data.chat_room_id === "number"
        ) {
          const chatRoomId = data.chat_room_id;

          setRooms((currentRooms) =>
            updateRoomOpponentOnline(
              currentRooms,
              chatRoomId,
              viewerRole,
              data.type === "user_online",
            ),
          );
        }
      });

      return () => {
        unsubscribe();
      };
    }, [refreshRooms, subscribe, user?.id, viewerRole]),
  );

  if (isLoading) {
    return (
      <View style={styles.centerBox}>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.centerText}>Loading chats...</Text>
      </View>
    );
  }

  if (rooms.length === 0) {
    return (
      <View style={styles.centerBox}>
        <Text style={styles.emptyTitle}>
          {message || "No chats yet"}
        </Text>
        <Text style={styles.centerText}>
          {message ? "Try again." : "Start a conversation from a provider profile."}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.list}>
      {message ? <Text style={styles.errorText}>{message}</Text> : null}

      {rooms.map((room) => (
        <ChatRoomPreviewItem
          key={room.id}
          onPress={(opponentName) =>
            navigation.navigate("ChatRoom", {
              chatRoomId: room.id,
              title: opponentName,
              opponentOnline: getOpponentOnline(room, viewerRole),
              providerProfileId: room.provider_profile_id,
            })
          }
          room={room}
          viewerRole={viewerRole}
        />
      ))}
    </View>
  );
}

function ChatRoomPreviewItem({
  room,
  viewerRole,
  onPress,
}: {
  room: ChatRoom;
  viewerRole: "customer" | "provider";
  onPress: (opponentName: string) => void;
}) {
  const opponentName = getOpponentName(room, viewerRole);
  const unreadCount = room.unread_count ?? 0;

  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => onPress(opponentName)}
      style={styles.roomItem}
    >
      <View style={styles.avatar}>
        <Text style={styles.avatarText}>{getAvatarText(opponentName)}</Text>
      </View>

      <View style={styles.roomMain}>
        <View style={styles.roomTitleRow}>
          <Text numberOfLines={1} style={styles.roomTitle}>
            {opponentName}
          </Text>
          <Text style={styles.timeText}>
            {formatChatTime(room.last_message_at ?? room.created_at)}
          </Text>
        </View>

        <Text numberOfLines={1} style={styles.previewText}>
          {formatLastMessagePreview(room.last_message)}
        </Text>
      </View>

      {unreadCount > 0 ? (
        <View style={styles.unreadBadge}>
          <Text style={styles.unreadText}>
            {unreadCount > 99 ? "99+" : unreadCount}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

function getOpponentName(room: ChatRoom, viewerRole: "customer" | "provider") {
  if (viewerRole === "customer") {
    return room.provider?.business_name || "Provider";
  }

  return room.customer?.name || "Customer";
}

function getOpponentOnline(room: ChatRoom, viewerRole: "customer" | "provider") {
  return viewerRole === "customer" ? room.provider_online : room.customer_online;
}

function getAvatarText(name: string) {
  return name.trim().slice(0, 1).toUpperCase() || "?";
}

function formatLastMessagePreview(message: ChatMessage | null) {
  if (!message) {
    return "No messages yet.";
  }

  if (message.attachments.length > 0 || message.message_type === "attachment") {
    const hasPicture = message.attachments.some((attachment) =>
      attachment.content_type.startsWith("image/"),
    );

    return hasPicture ? "[picture]" : "[file]";
  }

  if (message.message_type === "booking_created") {
    return "[booking] New booking request";
  }

  if (message.message_type === "booking_status") {
    return "[booking] Booking status updated";
  }

  return message.message || "No messages yet.";
}

function formatChatTime(value: string | null) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();

  if (isToday) {
    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  if (isYesterday) {
    return "Yesterday";
  }

  return date.toLocaleDateString([], {
    month: "2-digit",
    day: "2-digit",
  });
}

function isIncomingChatMessage(value: unknown): value is ChatMessage {
  return (
    Boolean(value) &&
    typeof value === "object" &&
    typeof (value as ChatMessage).id === "number" &&
    typeof (value as ChatMessage).chat_room_id === "number" &&
    typeof (value as ChatMessage).sender_id === "number"
  );
}

function updateRoomOpponentOnline(
  rooms: ChatRoom[],
  chatRoomId: number,
  viewerRole: "customer" | "provider",
  isOnline: boolean,
) {
  return rooms.map((room) => {
    if (room.id !== chatRoomId) {
      return room;
    }

    return viewerRole === "customer"
      ? { ...room, provider_online: isOnline }
      : { ...room, customer_online: isOnline };
  });
}

function applyChatMessageToRooms(
  rooms: ChatRoom[],
  chatMessage: ChatMessage,
  viewerUserId: number | null,
  unreadCountFromServer: number | null,
) {
  const roomIndex = rooms.findIndex((room) => room.id === chatMessage.chat_room_id);

  if (roomIndex < 0) {
    return rooms;
  }

  const room = rooms[roomIndex];
  const alreadyLatest = room.last_message?.id === chatMessage.id;
  const shouldIncrementUnread =
    !alreadyLatest && chatMessage.sender_id !== viewerUserId;
  const unreadCount = room.unread_count ?? 0;
  const updatedRoom: ChatRoom = {
    ...room,
    last_message: chatMessage,
    last_message_at: chatMessage.created_at,
    unread_count:
      unreadCountFromServer != null
        ? unreadCountFromServer
        : shouldIncrementUnread
          ? unreadCount + 1
          : unreadCount,
  };
  const nextRooms = [
    updatedRoom,
    ...rooms.slice(0, roomIndex),
    ...rooms.slice(roomIndex + 1),
  ];

  return nextRooms;
}

const styles = StyleSheet.create({
  list: {
    gap: spacing.xs,
  },
  centerBox: {
    minHeight: 220,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.lg,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
  },
  centerText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  errorText: {
    color: colors.danger,
    fontSize: 13,
  },
  roomItem: {
    minHeight: 74,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingVertical: spacing.sm,
  },
  avatar: {
    width: 48,
    height: 48,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: colors.surface,
  },
  avatarText: {
    color: colors.text,
    fontSize: 19,
    fontWeight: "700",
  },
  roomMain: {
    flex: 1,
    minWidth: 0,
    gap: spacing.xs,
  },
  roomTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  roomTitle: {
    flex: 1,
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
  },
  timeText: {
    color: colors.mutedText,
    fontSize: 12,
  },
  previewText: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 19,
  },
  unreadBadge: {
    minWidth: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.xs,
  },
  unreadText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
  },
});
