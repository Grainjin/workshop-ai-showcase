import {
  DefaultTheme,
  type LinkingOptions,
  NavigationContainer,
  useNavigation,
} from "@react-navigation/native";
import {
  createNativeStackNavigator,
  type NativeStackNavigationProp,
} from "@react-navigation/native-stack";
import type { ComponentType } from "react";
import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { AccountEditScreen } from "../screens/AccountEditScreen";
import { AccountSecurityScreen } from "../screens/AccountSecurityScreen";
import { AuthScreen } from "../screens/AuthScreen";
import { BookingHistoryScreen } from "../screens/BookingHistoryScreen";
import { ChatRoomScreen } from "../screens/ChatRoomScreen";
import { HelpScreen } from "../screens/HelpScreen";
import { LEGAL_DOCUMENTS, LegalScreen } from "../screens/LegalScreen";
import { NotificationsScreen } from "../screens/NotificationsScreen";
import { NotificationSettingsScreen } from "../screens/NotificationSettingsScreen";
import { PaymentsScreen } from "../screens/PaymentsScreen";
import { PaymentResultScreen } from "../screens/PaymentResultScreen";
import { VerifyEmailScreen } from "../screens/VerifyEmailScreen";
import { CustomerFavouritesScreen } from "../screens/customer/CustomerFavouritesScreen";
import { CustomerProviderDetailScreen } from "../screens/customer/CustomerProviderDetailScreen";
import { CustomerProviderPortfolioDetailScreen } from "../screens/customer/CustomerProviderPortfolioDetailScreen";
import { CustomerProviderSearchResultsScreen } from "../screens/customer/CustomerProviderSearchResultsScreen";
import { ProviderPortfolioCreateScreen } from "../screens/provider/ProviderPortfolioCreateScreen";
import { ProviderPortfolioDetailScreen } from "../screens/provider/ProviderPortfolioDetailScreen";
import { ProviderPortfolioListScreen } from "../screens/provider/ProviderPortfolioListScreen";
import {
  ProviderHomeScreen,
  ProviderIdentityVerificationScreen,
  ProviderServiceVerificationScreen,
  ProviderVerificationScreen,
} from "../screens/provider/ProviderHomeScreen";
import { ProviderPayoutAccountScreen } from "../screens/provider/ProviderPayoutAccountScreen";
import { ProviderOperatingSettingsScreen } from "../screens/provider/ProviderOperatingSettingsScreen";
import { useAuth } from "../context/AuthContext";
import { ProviderPayoutStatusProvider } from "../context/ProviderPayoutStatusContext";
import { consumePendingPaymentResult } from "../utils/pendingPaymentResult";
import {
  ProviderProfileGateProvider,
  useProviderProfileGate,
} from "../context/ProviderProfileGateContext";
import { RealtimeProvider } from "../context/RealtimeContext";
import { useIsWebDesktop } from "../layout/useIsWebDesktop";
import { colors } from "../theme/theme";
import { DesktopSidebar } from "./DesktopSidebar";
import { RoleTabs } from "./RoleTabs";
import type { RootStackParamList } from "./types";

export type { RootStackParamList } from "./types";

const Stack = createNativeStackNavigator<RootStackParamList>();

const linking: LinkingOptions<RootStackParamList> = {
  prefixes: [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:8090",
    "http://127.0.0.1:8090",
  ],
  config: {
    screens: {
      PaymentResult: "payment-result",
    },
  },
};

// The combined onboarding gate covers a provider's working surfaces only —
// chats and portfolios here, schedule and bookings in RoleTabs. Account and
// verification routes stay open so all three onboarding steps can be completed
// in any order.
const GuardedChatRoomScreen = withRequiredProviderProfile(ChatRoomScreen);
const GuardedProviderPortfolioListScreen = withRequiredProviderProfile(
  ProviderPortfolioListScreen,
);
const GuardedProviderPortfolioCreateScreen = withRequiredProviderProfile(
  ProviderPortfolioCreateScreen,
);
const GuardedProviderPortfolioDetailScreen = withRequiredProviderProfile(
  ProviderPortfolioDetailScreen,
);
const GuardedProviderOperatingSettingsScreen = withRequiredProviderProfile(
  ProviderOperatingSettingsScreen,
);

const navigationTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: colors.background,
    card: colors.background,
    primary: colors.primary,
    border: colors.border,
    text: colors.text,
  },
};

export function AppNavigator() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={styles.loadingScreen}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  // New accounts verify their email during sign-up. Older unverified
  // customers and providers confirm it here before anything else loads;
  // the backend refuses their other endpoints until then. Admins are exempt.
  const needsEmailVerification =
    user !== null && user.role !== "admin" && !user.email_verified;

  return (
    <NavigationContainer linking={linking} theme={navigationTheme}>
      {needsEmailVerification ? (
        <Stack.Navigator>
          <Stack.Screen
            name="VerifyEmail"
            component={VerifyEmailScreen}
            options={{ headerShown: false }}
          />
        </Stack.Navigator>
      ) : user ? (
        <RealtimeProvider>
          <ProviderPayoutStatusProvider>
            <ProviderProfileGateProvider>
              <AuthenticatedStack />
            </ProviderProfileGateProvider>
          </ProviderPayoutStatusProvider>
        </RealtimeProvider>
      ) : (
        <Stack.Navigator>
          <Stack.Screen
            name="Auth"
            component={AuthScreen}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="Legal"
            component={LegalScreen}
            options={legalScreenOptions}
          />
          <Stack.Screen
            name="PaymentResult"
            component={PaymentResultScreen}
            options={{ title: "Payment result" }}
          />
        </Stack.Navigator>
      )}
    </NavigationContainer>
  );
}

function AuthenticatedStack() {
  const isWebDesktop = useIsWebDesktop();
  const { user } = useAuth();
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  useEffect(() => {
    let isActive = true;
    void consumePendingPaymentResult().then((pendingResult) => {
      if (isActive && pendingResult) {
        navigation.navigate("PaymentResult", pendingResult);
      }
    });

    return () => {
      isActive = false;
    };
  }, [navigation, user?.id]);

  return (
    <Stack.Navigator
      layout={({ children }) => (
        <View style={[styles.shell, isWebDesktop ? styles.shellDesktop : null]}>
          {isWebDesktop ? <DesktopSidebar /> : null}
          <View style={styles.shellContent}>
            {children}
          </View>
        </View>
      )}
    >
      <Stack.Screen
        name="Main"
        component={RoleTabs}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="CustomerProviderDetail"
        component={CustomerProviderDetailScreen}
        options={{ title: "Provider" }}
      />
      <Stack.Screen
        name="CustomerProviderSearchResults"
        component={CustomerProviderSearchResultsScreen}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="CustomerProviderPortfolioDetail"
        component={CustomerProviderPortfolioDetailScreen}
        options={{ title: "Portfolio" }}
      />
      <Stack.Screen
        name="ChatRoom"
        component={GuardedChatRoomScreen}
        options={({ route }) => ({
          title: route.params.title,
        })}
      />
      <Stack.Screen
        name="AccountEdit"
        component={AccountEditScreen}
        options={{ title: "Edit profile" }}
      />
      <Stack.Screen
        name="ProviderVerification"
        component={ProviderVerificationScreen}
        options={{ title: "Verification" }}
      />
      <Stack.Screen
        name="ProviderIdentityVerification"
        component={ProviderIdentityVerificationScreen}
        options={{ title: "ID verification" }}
      />
      <Stack.Screen
        name="ProviderServiceVerification"
        component={ProviderServiceVerificationScreen}
        options={{ title: "Service verification" }}
      />
      <Stack.Screen
        name="ProviderPayoutAccount"
        component={ProviderPayoutAccountScreen}
        options={{ title: "Payout account" }}
      />
      <Stack.Screen
        name="ProviderOperatingSettings"
        component={GuardedProviderOperatingSettingsScreen}
        options={{ title: "Operating settings" }}
      />
      <Stack.Screen
        name="AccountSecurity"
        component={AccountSecurityScreen}
        options={{ title: "Account and Security" }}
      />
      <Stack.Screen
        name="Help"
        component={HelpScreen}
        options={{ title: "Help and Support" }}
      />
      {/* Not gated: a provider with an incomplete profile must still be able
          to read the terms they are asked to accept. */}
      <Stack.Screen
        name="Legal"
        component={LegalScreen}
        options={legalScreenOptions}
      />
      <Stack.Screen
        name="BookingHistory"
        component={BookingHistoryScreen}
        options={{ title: "Booking history" }}
      />
      <Stack.Screen
        name="Notifications"
        component={NotificationsScreen}
        options={{ title: "Notifications" }}
      />
      <Stack.Screen
        name="NotificationSettings"
        component={NotificationSettingsScreen}
        options={{ title: "Notification settings" }}
      />
      <Stack.Screen
        name="Payments"
        component={PaymentsScreen}
        options={{ title: "Payments" }}
      />
      <Stack.Screen
        name="PaymentResult"
        component={PaymentResultScreen}
        options={{ title: "Payment result" }}
      />
      <Stack.Screen
        name="CustomerFavourites"
        component={CustomerFavouritesScreen}
        options={{ title: "Favourites" }}
      />
      <Stack.Screen
        name="ProviderPortfolioList"
        component={GuardedProviderPortfolioListScreen}
        options={{ title: "Portfolios" }}
      />
      <Stack.Screen
        name="ProviderPortfolioCreate"
        component={GuardedProviderPortfolioCreateScreen}
        options={{ title: "Add portfolio" }}
      />
      <Stack.Screen
        name="ProviderPortfolioDetail"
        component={GuardedProviderPortfolioDetailScreen}
        options={{ title: "Portfolio" }}
      />
    </Stack.Navigator>
  );
}

// Registered in both stacks: register happens signed out, and both roles can
// open the same pages once signed in.
function legalScreenOptions({
  route,
}: {
  route: { params: RootStackParamList["Legal"] };
}) {
  return { title: LEGAL_DOCUMENTS[route.params.document].title };
}

function withRequiredProviderProfile<P extends object>(
  ScreenComponent: ComponentType<P>,
) {
  return function RequiredProviderProfileStackScreen(props: P) {
    const { user } = useAuth();
    const {
      isProviderProfileLoading,
      isProviderProfileRequired,
      showProviderProfileRequiredMessage,
    } = useProviderProfileGate();
    const navigation =
      useNavigation<NativeStackNavigationProp<RootStackParamList>>();

    useEffect(() => {
      if (user?.role === "provider" && isProviderProfileRequired) {
        showProviderProfileRequiredMessage();
        navigation.reset({
          index: 0,
          routes: [
            {
              name: "Main",
              params: {
                screen: "ProviderHome",
              },
            },
          ],
        });
      }
    }, [
      isProviderProfileRequired,
      navigation,
      showProviderProfileRequiredMessage,
      user?.role,
    ]);

    if (user?.role === "provider" && isProviderProfileLoading) {
      return (
        <View style={styles.loadingScreen}>
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

const styles = StyleSheet.create({
  loadingScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  shell: {
    flex: 1,
  },
  shellDesktop: {
    flexDirection: "row",
  },
  shellContent: {
    flex: 1,
    minWidth: 0,
  },
});
