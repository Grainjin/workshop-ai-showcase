import { useFocusEffect } from "@react-navigation/native";
import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  getNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
} from "../api/notifications";
import { SecondaryButton } from "../components/SecondaryButton";
import { useRealtime } from "../context/RealtimeContext";
import { colors, radius, spacing } from "../theme/theme";
import type { PaginatedData } from "../types/chat";
import type { Notification } from "../types/notification";
import { getErrorMessage } from "../utils/errors";

const PAGE_SIZE = 30;

export function NotificationsScreen() {
  const { notificationUnreadCount, refreshUnreadCounts } = useRealtime();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [paging, setPaging] = useState<PaginatedData<Notification> | null>(null);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isMarkingAllRead, setIsMarkingAllRead] = useState(false);
  const [message, setMessage] = useState("");

  const loadNotifications = useCallback(async () => {
    setIsLoading(true);
    setMessage("");
    try {
      const result = await getNotifications(1, PAGE_SIZE);
      setNotifications(result?.items ?? []);
      setPaging(result);
      setPage(1);
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void loadNotifications();
    }, [loadNotifications]),
  );

  async function loadMore() {
    if (isLoadingMore || !paging?.has_next) {
      return;
    }

    setIsLoadingMore(true);
    try {
      const nextPage = page + 1;
      const result = await getNotifications(nextPage, PAGE_SIZE);
      if (result) {
        setNotifications((current) => [...current, ...result.items]);
        setPaging(result);
        setPage(nextPage);
      }
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function openNotification(notification: Notification) {
    if (notification.read_at) {
      return;
    }

    try {
      const result = await markNotificationAsRead(notification.id);
      if (result?.notification) {
        setNotifications((current) =>
          current.map((item) =>
            item.id === notification.id ? result.notification : item,
          ),
        );
        void refreshUnreadCounts();
      }
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  }

  async function markAllAsRead() {
    if (isMarkingAllRead || notificationUnreadCount <= 0) {
      return;
    }

    setIsMarkingAllRead(true);
    setMessage("");
    try {
      await markAllNotificationsAsRead();
      const readAt = new Date().toISOString();
      setNotifications((current) =>
        current.map((notification) => ({ ...notification, read_at: readAt })),
      );
      await refreshUnreadCounts();
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsMarkingAllRead(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.content} style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Notifications</Text>
        <View style={styles.headerActions}>
          <SecondaryButton
            disabled={
              isLoading || isLoadingMore || isMarkingAllRead || notificationUnreadCount <= 0
            }
            label="Mark all as read"
            onPress={() => void markAllAsRead()}
          />
          <SecondaryButton
            disabled={isLoading || isLoadingMore || isMarkingAllRead}
            label="Refresh"
            onPress={() => void loadNotifications()}
          />
        </View>
      </View>

      {message ? <Text style={styles.errorText}>{message}</Text> : null}

      {isLoading ? (
        <ActivityIndicator color={colors.primary} style={styles.loader} />
      ) : notifications.length === 0 ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyTitle}>No notifications yet</Text>
          <Text style={styles.emptyText}>Bookings, complaints, and review results appear here.</Text>
        </View>
      ) : (
        <View style={styles.list}>
          {notifications.map((notification) => (
            <NotificationCard
              key={notification.id}
              notification={notification}
              onPress={() => void openNotification(notification)}
            />
          ))}
        </View>
      )}

      {paging?.has_next ? (
        <SecondaryButton
          disabled={isLoadingMore}
          label={isLoadingMore ? "Loading..." : "Load more"}
          onPress={() => void loadMore()}
        />
      ) : null}
    </ScrollView>
  );
}

function NotificationCard({
  notification,
  onPress,
}: {
  notification: Notification;
  onPress: () => void;
}) {
  const isUnread = !notification.read_at;

  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.notificationCard,
        isUnread ? styles.unreadCard : null,
        pressed ? styles.cardPressed : null,
      ]}
    >
      <View style={styles.notificationHeader}>
        <Text numberOfLines={1} style={styles.notificationTitle}>
          {notification.title}
        </Text>
        {isUnread ? <View style={styles.unreadDot} /> : null}
      </View>
      <Text style={styles.notificationContent}>{notification.content}</Text>
      <Text style={styles.notificationMeta}>
        {formatDate(notification.created_at)}
      </Text>
    </Pressable>
  );
}

function formatDate(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value.slice(0, 10);
  }

  return date.toLocaleString();
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.surface,
  },
  content: {
    gap: spacing.md,
    padding: spacing.lg,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.md,
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  title: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "800",
  },
  loader: {
    paddingVertical: spacing.xl,
  },
  errorText: {
    color: colors.danger,
    fontSize: 14,
    lineHeight: 20,
  },
  emptyCard: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "800",
  },
  emptyText: {
    color: colors.mutedText,
    fontSize: 14,
  },
  list: {
    gap: spacing.md,
  },
  notificationCard: {
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  unreadCard: {
    borderColor: colors.primary,
  },
  cardPressed: {
    backgroundColor: colors.surface,
  },
  notificationHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  notificationTitle: {
    flex: 1,
    color: colors.text,
    fontSize: 17,
    fontWeight: "800",
  },
  unreadDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.primary,
  },
  notificationContent: {
    color: colors.text,
    fontSize: 14,
    lineHeight: 21,
  },
  notificationMeta: {
    color: colors.mutedText,
    fontSize: 12,
  },
});
