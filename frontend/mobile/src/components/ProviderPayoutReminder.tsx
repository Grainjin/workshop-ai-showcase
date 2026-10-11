import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { AlertCircle, ArrowRight } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "../context/AuthContext";
import { useProviderPayoutStatus } from "../context/ProviderPayoutStatusContext";
import type { RootStackParamList } from "../navigation/types";
import { colors, radius, spacing } from "../theme/theme";

export function ProviderPayoutReminder() {
  const { user } = useAuth();
  const { status } = useProviderPayoutStatus();
  const navigation =
    useNavigation<NativeStackNavigationProp<RootStackParamList>>();

  if (user?.role !== "provider" || status === null || status === "active") {
    return null;
  }

  return (
    <View pointerEvents="box-none" style={styles.overlay}>
      <Pressable
        accessibilityLabel="Complete payout details"
        accessibilityRole="button"
        onPress={() => navigation.navigate("ProviderPayoutAccount")}
        style={({ pressed }) => [
          styles.reminder,
          pressed ? styles.reminderPressed : null,
        ]}
      >
        <View style={styles.iconWrap}>
          <AlertCircle color={colors.danger} size={20} />
        </View>
        <View style={styles.copy}>
          <Text style={styles.title}>Complete payout details</Text>
          <Text style={styles.message}>
            Complete your details in Account → Payout account.
          </Text>
        </View>
        <ArrowRight color={colors.danger} size={20} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: "absolute",
    top: spacing.md,
    left: spacing.md,
    right: spacing.md,
    alignItems: "center",
    zIndex: 20,
    elevation: 10,
  },
  reminder: {
    width: "100%",
    maxWidth: 680,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: "#F1B9B4",
    borderRadius: radius.md,
    backgroundColor: "#FFF4F2",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    shadowColor: "#7A211A",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
  },
  reminderPressed: {
    opacity: 0.82,
  },
  iconWrap: {
    alignItems: "center",
    justifyContent: "center",
  },
  copy: {
    flex: 1,
    gap: 2,
  },
  title: {
    color: "#8F2922",
    fontSize: 14,
    fontWeight: "800",
  },
  message: {
    color: "#9C4942",
    fontSize: 13,
    lineHeight: 18,
  },
});
