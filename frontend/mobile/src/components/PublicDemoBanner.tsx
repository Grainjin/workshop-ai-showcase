import { StyleSheet, Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DEMO_MODE } from "../config/env";
import { colors, spacing } from "../theme/theme";

export function PublicDemoBanner() {
  if (!DEMO_MODE) return null;

  return (
    <SafeAreaView edges={["top"]} style={styles.banner}>
      <Text
        accessibilityLabel="Public Demo — simulated data and payments"
        style={styles.text}
      >
        Public Demo — simulated data and payments
      </Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  banner: { backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border },
  text: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
});
