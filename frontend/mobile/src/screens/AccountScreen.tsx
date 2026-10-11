import * as ImagePicker from "expo-image-picker";
import {
  BellRing,
  BadgeCheck,
  ChevronRight,
  CircleHelp,
  CreditCard,
  Heart,
  History,
  LogOut,
  Pencil,
  Plus,
  LockKeyhole,
  Shield,
  SlidersHorizontal,
  UserRound,
} from "lucide-react-native";
import { ReactNode, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { ScreenContainer } from "../components/ScreenContainer";
import { useAuth } from "../context/AuthContext";
import { useProviderProfileGate } from "../context/ProviderProfileGateContext";
import { useIsWebDesktop } from "../layout/useIsWebDesktop";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { colors, radius, spacing } from "../theme/theme";
import { resolveMediaUrl } from "../utils/media";

type MenuItemProps = {
  badgeCount?: number;
  icon: ReactNode;
  label: string;
  onPress?: () => void;
  isDanger?: boolean;
};

export function AccountScreen() {
  const { user, signOut, uploadAvatar } = useAuth();
  const {
    hasProviderProfile,
    showProviderProfileRequiredMessage,
  } = useProviderProfileGate();
  const isCustomer = user?.role === "customer";
  const isProvider = user?.role === "provider";
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const isWebDesktop = useIsWebDesktop();
  const [message, setMessage] = useState("");
  const avatarUri = resolveMediaUrl(user?.avatar_url ?? null);


  async function handlePickAvatar() {
    setMessage("");

    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setMessage("Allow access to photos to update your avatar.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      allowsEditing: true,
      aspect: [1, 1],
      mediaTypes: ["images"],
      quality: 0.85,
    });

    if (result.canceled || !result.assets[0]?.uri) {
      return;
    }

    try {
      const asset = result.assets[0];
      await uploadAvatar({
        uri: asset.uri,
        fileName: asset.fileName,
        mimeType: asset.mimeType,
      });
      setMessage("Avatar updated");
    } catch {
      setMessage("Couldn't update avatar. Try again.");
    }
  }

  return (
    <ScreenContainer contentStyle={styles.content}>
      <View style={isWebDesktop ? styles.desktopRow : undefined}>
        <View
          style={[
            styles.profileHeader,
            isWebDesktop ? styles.profileHeaderDesktop : null,
          ]}
        >
          <Pressable
            accessibilityLabel="Upload avatar"
            accessibilityRole="button"
            onPress={() => {
              void handlePickAvatar();
            }}
            style={styles.avatarButton}
          >
            {avatarUri ? (
              <Image
                resizeMode="cover"
                source={{ uri: avatarUri }}
                style={styles.avatarImage}
              />
            ) : (
              <View style={styles.avatarPlaceholder}>
                <UserRound color={colors.mutedText} size={44} />
              </View>
            )}

            {!avatarUri ? (
              <View style={styles.avatarAddBadge}>
                <Plus color="#FFFFFF" size={22} />
              </View>
            ) : null}
          </Pressable>

          <Text style={styles.userName} numberOfLines={1}>
            {user?.name ?? "Workshop AI"}
          </Text>
          <Text style={styles.userMeta} numberOfLines={1}>
            {user?.email}
          </Text>
          {message ? <Text style={styles.messageText}>{message}</Text> : null}
        </View>

        <View style={styles.menuColumn}>
          <View style={styles.menuCard}>
            <MenuItem
              icon={<Pencil color={colors.text} size={24} />}
              label="Edit profile"
              onPress={() =>
                navigation.navigate("AccountEdit")
              }
            />
            {isProvider ? (
              <MenuItem
                icon={<BadgeCheck color={colors.text} size={24} />}
                label="Verification"
                onPress={() => navigation.navigate("ProviderVerification")}
              />
            ) : null}
            {isProvider ? (
              <MenuItem
                icon={
                  hasProviderProfile === true ? (
                    <SlidersHorizontal color={colors.text} size={24} />
                  ) : (
                    <LockKeyhole color={colors.mutedText} size={24} />
                  )
                }
                label="Operating settings"
                onPress={() => {
                  if (hasProviderProfile === true) {
                    navigation.navigate("ProviderOperatingSettings");
                  } else {
                    showProviderProfileRequiredMessage();
                  }
                }}
              />
            ) : null}
          </View>

          <View style={styles.menuCard}>
            <MenuItem
              icon={<Shield color={colors.text} size={24} />}
              label="Account and Security"
              onPress={() =>
                navigation.navigate("AccountSecurity")
              }
            />
            <MenuItem
              icon={<History color={colors.text} size={24} />}
              label="Booking history"
              onPress={() =>
                navigation.navigate("BookingHistory")
              }
            />
            {isCustomer ? (
              <MenuItem
                icon={<Heart color={colors.text} size={24} />}
                label="Favourites"
                onPress={() =>
                  navigation.navigate("CustomerFavourites")
                }
              />
            ) : null}
            <MenuItem
              icon={<CreditCard color={colors.text} size={24} />}
              label="Payments"
              onPress={() =>
                navigation.navigate("Payments")
              }
            />
            <MenuItem
              icon={<BellRing color={colors.text} size={24} />}
              label="Notification settings"
              onPress={() =>
                navigation.navigate("NotificationSettings")
              }
            />
            <MenuItem
              icon={<CircleHelp color={colors.text} size={24} />}
              label="Help and Support"
              onPress={() =>
                navigation.navigate("Help")
              }
            />
          </View>

          <View style={styles.menuCard}>
            <MenuItem
              icon={<LogOut color={colors.danger} size={24} />}
              isDanger
              label="Sign out"
              onPress={() => void signOut()}
            />
          </View>
        </View>
      </View>
    </ScreenContainer>
  );
}

function MenuItem({
  badgeCount = 0,
  icon,
  label,
  onPress,
  isDanger = false,
}: MenuItemProps) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [
        styles.menuItem,
        pressed && onPress ? styles.menuItemPressed : null,
      ]}
    >
      <View style={styles.menuIcon}>{icon}</View>
      <Text style={[styles.menuLabel, isDanger ? styles.dangerText : null]}>
        {label}
      </Text>
      {badgeCount > 0 ? (
        <View style={styles.menuBadge}>
          <Text style={styles.menuBadgeText}>
            {badgeCount > 99 ? "99+" : badgeCount}
          </Text>
        </View>
      ) : null}
      <ChevronRight color={colors.mutedText} size={22} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  content: {
    backgroundColor: "#F7F7F8",
    paddingTop: spacing.xl,
  },
  desktopRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.lg,
  },
  profileHeader: {
    alignItems: "center",
    gap: spacing.sm,
    paddingTop: spacing.lg,
    paddingBottom: spacing.lg,
  },
  profileHeaderDesktop: {
    width: 280,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: spacing.lg,
  },
  menuColumn: {
    flex: 1,
    minWidth: 0,
    gap: spacing.md,
  },
  avatarButton: {
    width: 104,
    height: 104,
  },
  avatarImage: {
    width: "100%",
    height: "100%",
    borderRadius: 24,
    backgroundColor: colors.surface,
  },
  avatarPlaceholder: {
    width: "100%",
    height: "100%",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 24,
    backgroundColor: "#FFFFFF",
  },
  avatarAddBadge: {
    position: "absolute",
    right: -5,
    bottom: -5,
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 3,
    borderColor: "#FFFFFF",
    borderRadius: 18,
    backgroundColor: colors.primary,
  },
  userName: {
    maxWidth: "86%",
    color: colors.text,
    fontSize: 32,
    fontWeight: "800",
  },
  userMeta: {
    maxWidth: "86%",
    color: colors.mutedText,
    fontSize: 14,
  },
  messageText: {
    color: colors.danger,
    fontSize: 13,
  },
  menuCard: {
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 18,
    backgroundColor: "#FFFFFF",
  },
  menuItem: {
    minHeight: 64,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingHorizontal: spacing.lg,
  },
  menuItemPressed: {
    backgroundColor: colors.surface,
  },
  menuIcon: {
    width: 28,
    alignItems: "center",
  },
  menuLabel: {
    flex: 1,
    color: colors.text,
    fontSize: 18,
    fontWeight: "600",
  },
  menuBadge: {
    minWidth: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.xs,
  },
  menuBadgeText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
  },
  dangerText: {
    color: colors.danger,
  },
});
