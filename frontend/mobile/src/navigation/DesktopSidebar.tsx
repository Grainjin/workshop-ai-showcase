import { useNavigation, useNavigationState } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { ComponentType } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../context/AuthContext";
import { useProviderProfileGate } from "../context/ProviderProfileGateContext";
import { useRealtime } from "../context/RealtimeContext";
import { colors, layout, spacing } from "../theme/theme";
import { tabIcons } from "./tabIcons";
import type { MainTabParamList, RootStackParamList } from "./types";

type SidebarItem = {
  tab: keyof MainTabParamList;
  label: string;
  icon: ComponentType<{ color: string; size: number }>;
  badge?: number;
  stackRoutes?: Array<keyof RootStackParamList>;
};

export function DesktopSidebar() {
  const { user } = useAuth();
  const { isProviderProfileRequired, showProviderProfileRequiredMessage } =
    useProviderProfileGate();
  const { chatUnreadCount, notificationUnreadCount } = useRealtime();
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const defaultTab =
    user?.role === "admin"
      ? "AdminDashboard"
      : user?.role === "provider"
        ? "ProviderHome"
        : "CustomerHome";
  const active = useActiveDesktopRoute(defaultTab);
  const items = getSidebarItems(
    user?.role,
    chatUnreadCount,
    notificationUnreadCount,
  );

  return (
    <View style={styles.sidebar}>
      <Text style={styles.brand}>Workshop AI</Text>
      <View style={styles.nav}>
        {items.map((item) => {
          const isActive =
            active.tab === item.tab ||
            (active.stack !== "Main" &&
              item.stackRoutes?.includes(
                active.stack as keyof RootStackParamList,
              ));

          return (
            <Pressable
              accessibilityRole="button"
              key={item.tab}
              onPress={() => {
                if (
                  user?.role === "provider" &&
                  isProviderProfileRequired &&
                  item.tab !== "ProviderHome" &&
                  item.tab !== "Account"
                ) {
                  showProviderProfileRequiredMessage();
                  return;
                }

                navigation.navigate("Main", { screen: item.tab });
              }}
              style={[styles.item, isActive ? styles.itemActive : null]}
            >
              <item.icon
                color={isActive ? colors.primary : colors.mutedText}
                size={20}
              />
              <Text
                style={[
                  styles.itemLabel,
                  isActive ? styles.itemLabelActive : null,
                ]}
              >
                {item.label}
              </Text>
              {item.badge ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>
                    {item.badge > 99 ? "99+" : item.badge}
                  </Text>
                </View>
              ) : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function useActiveDesktopRoute(defaultTab: keyof MainTabParamList) {
  return useNavigationState((state) => {
    const route = state.routes[state.index];
    if (route.name === "Main") {
      const tabState = route.state;
      const tabIndex =
        tabState && "index" in tabState ? (tabState.index ?? 0) : 0;
      const tabRoute = tabState?.routes?.[tabIndex];
      return {
        stack: "Main",
        tab: (tabRoute?.name ?? defaultTab) as keyof MainTabParamList,
      };
    }

    return {
      stack: route.name,
      tab: undefined as keyof MainTabParamList | undefined,
    };
  });
}

function getSidebarItems(
  role: string | undefined,
  chatUnreadCount: number,
  notificationUnreadCount: number,
): SidebarItem[] {
  const accountItem: SidebarItem = {
    tab: "Account",
    label: "Account",
    icon: tabIcons.account,
    badge: notificationUnreadCount,
    stackRoutes: [
      "AccountEdit",
      "ProviderVerification",
      "ProviderPayoutAccount",
      "ProviderOperatingSettings",
      "AccountSecurity",
      "Help",
      "Legal",
      "BookingHistory",
      "Notifications",
      "NotificationSettings",
      "Payments",
      "CustomerFavourites",
    ],
  };

  if (role === "provider") {
    return [
      {
        tab: "ProviderHome",
        label: "Home",
        icon: tabIcons.home,
        stackRoutes: [
          "ProviderPortfolioList",
          "ProviderPortfolioCreate",
          "ProviderPortfolioDetail",
        ],
      },
      { tab: "ProviderSchedule", label: "Schedule", icon: tabIcons.schedule },
      { tab: "ProviderBookings", label: "Bookings", icon: tabIcons.bookings },
      {
        tab: "ProviderChats",
        label: "Chats",
        icon: tabIcons.chats,
        badge: chatUnreadCount,
        stackRoutes: ["ChatRoom"],
      },
      accountItem,
    ];
  }

  if (role === "admin") {
    return [
      { tab: "AdminDashboard", label: "Admin", icon: tabIcons.admin },
      accountItem,
    ];
  }

  return [
    {
      tab: "CustomerHome",
      label: "Home",
      icon: tabIcons.home,
      stackRoutes: [
        "CustomerProviderDetail",
        "CustomerProviderSearchResults",
        "CustomerProviderPortfolioDetail",
      ],
    },
    {
      tab: "CustomerChats",
      label: "Chats",
      icon: tabIcons.chats,
      badge: chatUnreadCount,
      stackRoutes: ["ChatRoom"],
    },
    { tab: "CustomerAIChat", label: "AI Chat", icon: tabIcons.aiChat },
    { tab: "CustomerBookings", label: "Bookings", icon: tabIcons.bookings },
    accountItem,
  ];
}

const styles = StyleSheet.create({
  sidebar: {
    width: layout.webSidebarWidth,
    borderRightWidth: 1,
    borderRightColor: colors.border,
    backgroundColor: colors.background,
    paddingTop: spacing.xl,
    paddingHorizontal: spacing.md,
  },
  brand: {
    color: colors.primary,
    fontSize: 16,
    fontWeight: "800",
    marginBottom: spacing.lg,
    paddingHorizontal: spacing.sm,
  },
  nav: {
    gap: spacing.xs,
  },
  item: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderRadius: 10,
    paddingHorizontal: spacing.sm,
  },
  itemActive: {
    backgroundColor: "#E9F7F3",
  },
  itemLabel: {
    flex: 1,
    color: colors.mutedText,
    fontSize: 15,
    fontWeight: "600",
  },
  itemLabelActive: {
    color: colors.primary,
  },
  badge: {
    minWidth: 20,
    height: 20,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 10,
    backgroundColor: colors.primary,
    paddingHorizontal: 6,
  },
  badgeText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "800",
  },
});
