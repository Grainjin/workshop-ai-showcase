import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import type { BottomTabNavigationProp } from "@react-navigation/bottom-tabs";
import type { BottomTabBarButtonProps } from "@react-navigation/bottom-tabs";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { Bell } from "lucide-react-native";
import type { ComponentType } from "react";
import { useEffect } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { useIsWebDesktop } from "../layout/useIsWebDesktop";
import { useAuth } from "../context/AuthContext";
import { useProviderProfileGate } from "../context/ProviderProfileGateContext";
import { useRealtime } from "../context/RealtimeContext";
import { AccountScreen } from "../screens/AccountScreen";
import { AdminDashboardScreen } from "../screens/admin/AdminDashboardScreen";
import { CustomerAIChatScreen } from "../screens/customer/CustomerAIChatScreen";
import { CustomerBookingsScreen } from "../screens/customer/CustomerBookingsScreen";
import { CustomerChatsScreen } from "../screens/customer/CustomerChatsScreen";
import { CustomerHomeScreen } from "../screens/customer/CustomerHomeScreen";
import { ProviderBookingsScreen } from "../screens/provider/ProviderBookingsScreen";
import { ProviderChatsScreen } from "../screens/provider/ProviderChatsScreen";
import { ProviderHomeScreen } from "../screens/provider/ProviderHomeScreen";
import { ProviderScheduleScreen } from "../screens/provider/ProviderScheduleScreen";
import { colors } from "../theme/theme";
import { tabIcons } from "./tabIcons";
import type { MainTabParamList, RootStackParamList } from "./types";

export type { MainTabParamList } from "./types";

const Tab = createBottomTabNavigator<MainTabParamList>();

const GuardedProviderScheduleScreen = withRequiredProviderProfile(
  ProviderScheduleScreen,
);
const GuardedProviderBookingsScreen = withRequiredProviderProfile(
  ProviderBookingsScreen,
);
const GuardedProviderChatsScreen =
  withRequiredProviderProfile(ProviderChatsScreen);

export function RoleTabs() {
  const { user } = useAuth();
  const { isProviderProfileRequired, showProviderProfileRequiredMessage } =
    useProviderProfileGate();
  const { chatUnreadCount, notificationUnreadCount } = useRealtime();
  const isWebDesktop = useIsWebDesktop();
  const providerBlockedTabButton = isProviderProfileRequired
    ? buildProviderBlockedTabButton(showProviderProfileRequiredMessage)
    : undefined;

  const initialRouteName =
    user?.role === "admin"
      ? "AdminDashboard"
      : user?.role === "provider"
        ? "ProviderHome"
        : "CustomerHome";

  return (
    <Tab.Navigator
      initialRouteName={initialRouteName}
      screenOptions={{
        headerStyle: {
          backgroundColor: colors.background,
        },
        headerShadowVisible: false,
        headerTitleStyle: {
          color: colors.text,
          fontWeight: "700",
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.mutedText,
        tabBarBadgeStyle: {
          backgroundColor: colors.primary,
          color: "#FFFFFF",
          fontSize: 11,
          fontWeight: "800",
        },
        ...(isWebDesktop
          ? {
              tabBarStyle: {
                display: "none" as const,
                height: 0,
              },
            }
          : {
              tabBarStyle: {
                borderTopColor: colors.border,
                backgroundColor: colors.background,
              },
            }),
      }}
    >
      {user?.role === "customer" ? (
        <>
          <Tab.Screen
            name="CustomerHome"
            component={CustomerHomeScreen}
            options={{
              title: "Home",
              tabBarLabel: "Home",
              tabBarIcon: tabIcons.home,
            }}
          />
          <Tab.Screen
            name="CustomerChats"
            component={CustomerChatsScreen}
            options={{
              title: "Chats",
              tabBarLabel: "Chats",
              tabBarIcon: tabIcons.chats,
              tabBarBadge: formatUnreadBadge(chatUnreadCount),
            }}
          />
          <Tab.Screen
            name="CustomerAIChat"
            component={CustomerAIChatScreen}
            options={{
              title: "AI Chat",
              tabBarLabel: "AI Chat",
              tabBarIcon: tabIcons.aiChat,
            }}
          />
          <Tab.Screen
            name="CustomerBookings"
            component={CustomerBookingsScreen}
            options={{
              title: "Bookings",
              tabBarLabel: "Bookings",
              tabBarIcon: tabIcons.bookings,
            }}
          />
        </>
      ) : null}

      {user?.role === "provider" ? (
        <>
          <Tab.Screen
            name="ProviderHome"
            component={ProviderHomeScreen}
            options={{
              title: "Home",
              tabBarLabel: "Home",
              tabBarIcon: tabIcons.home,
            }}
          />
          <Tab.Screen
            name="ProviderSchedule"
            component={GuardedProviderScheduleScreen}
            listeners={{
              tabPress: (event) => {
                if (isProviderProfileRequired) {
                  event.preventDefault();
                  showProviderProfileRequiredMessage();
                }
              },
            }}
            options={{
              title: "Schedule",
              tabBarLabel: "Schedule",
              tabBarIcon: tabIcons.schedule,
              tabBarButton: providerBlockedTabButton,
            }}
          />
          <Tab.Screen
            name="ProviderBookings"
            component={GuardedProviderBookingsScreen}
            listeners={{
              tabPress: (event) => {
                if (isProviderProfileRequired) {
                  event.preventDefault();
                  showProviderProfileRequiredMessage();
                }
              },
            }}
            options={{
              title: "Bookings",
              tabBarLabel: "Bookings",
              tabBarIcon: tabIcons.bookings,
              tabBarButton: providerBlockedTabButton,
            }}
          />
          <Tab.Screen
            name="ProviderChats"
            component={GuardedProviderChatsScreen}
            listeners={{
              tabPress: (event) => {
                if (isProviderProfileRequired) {
                  event.preventDefault();
                  showProviderProfileRequiredMessage();
                }
              },
            }}
            options={{
              title: "Chats",
              tabBarLabel: "Chats",
              tabBarIcon: tabIcons.chats,
              tabBarBadge: formatUnreadBadge(chatUnreadCount),
              tabBarButton: providerBlockedTabButton,
            }}
          />
        </>
      ) : null}

      {user?.role === "admin" ? (
        <Tab.Screen
          name="AdminDashboard"
          component={AdminDashboardScreen}
          options={{
            title: "Admin",
            tabBarLabel: "Admin",
            tabBarIcon: tabIcons.admin,
          }}
        />
      ) : null}

      <Tab.Screen
        name="Account"
        component={AccountScreen}
        options={{
          title: "Account",
          tabBarLabel: "Account",
          tabBarIcon: tabIcons.account,
          tabBarBadge: formatUnreadBadge(notificationUnreadCount),
          headerRight: () => (
            <NotificationsHeaderButton unreadCount={notificationUnreadCount} />
          ),
        }}
      />
    </Tab.Navigator>
  );
}

function formatUnreadBadge(count: number) {
  if (count <= 0) {
    return undefined;
  }

  return count > 99 ? "99+" : count;
}

/**
 * The notification inbox lives in the Account header so it stays one tap away
 * while the Account menu groups settings.
 */
function NotificationsHeaderButton({ unreadCount }: { unreadCount: number }) {
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  return (
    <Pressable
      accessibilityLabel={
        unreadCount > 0
          ? `Notifications, ${unreadCount} unread`
          : "Notifications"
      }
      accessibilityRole="button"
      hitSlop={8}
      onPress={() => navigation.navigate("Notifications")}
      style={({ pressed }) => [
        headerStyles.button,
        pressed ? headerStyles.buttonPressed : null,
      ]}
    >
      <Bell color={colors.text} size={22} />
      {unreadCount > 0 ? (
        <View style={headerStyles.badge}>
          <Text style={headerStyles.badgeText}>
            {unreadCount > 99 ? "99+" : unreadCount}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const headerStyles = StyleSheet.create({
  button: {
    marginRight: 16,
    padding: 4,
  },
  buttonPressed: {
    opacity: 0.6,
  },
  badge: {
    position: "absolute",
    top: -2,
    right: -4,
    minWidth: 18,
    height: 18,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 9,
    backgroundColor: colors.primary,
    paddingHorizontal: 4,
  },
  badgeText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: "800",
  },
});

function buildProviderBlockedTabButton(
  showProviderProfileRequiredMessage: () => void,
) {
  return function ProviderBlockedTabButton(props: BottomTabBarButtonProps) {
    return (
      <Pressable
        accessibilityLabel={props.accessibilityLabel}
        accessibilityRole={props.accessibilityRole}
        accessibilityState={props.accessibilityState}
        onLongPress={props.onLongPress}
        onPress={() => {
          showProviderProfileRequiredMessage();
        }}
        style={props.style}
        testID={props.testID}
      >
        {props.children}
      </Pressable>
    );
  };
}

function withRequiredProviderProfile<P extends object>(
  ScreenComponent: ComponentType<P>,
) {
  return function RequiredProviderProfileScreen(props: P) {
    const { user } = useAuth();
    const {
      isProviderProfileLoading,
      isProviderProfileRequired,
      showProviderProfileRequiredMessage,
    } = useProviderProfileGate();
    const navigation =
      useNavigation<BottomTabNavigationProp<MainTabParamList>>();

    useEffect(() => {
      if (user?.role === "provider" && isProviderProfileRequired) {
        showProviderProfileRequiredMessage();
        navigation.navigate("ProviderHome");
      }
    }, [
      isProviderProfileRequired,
      navigation,
      showProviderProfileRequiredMessage,
      user?.role,
    ]);

    if (user?.role === "provider" && isProviderProfileLoading) {
      return (
        <View style={guardStyles.loader}>
          <ActivityIndicator color={colors.primary} />
        </View>
      );
    }

    if (user?.role === "provider" && isProviderProfileRequired) {
      return null;
    }

    return <ScreenComponent {...props} />;
  };
}

const guardStyles = StyleSheet.create({
  loader: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
});
