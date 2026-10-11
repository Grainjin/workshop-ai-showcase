import { StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "../theme/theme";
import type { ReferencePriceRange as ReferencePriceRangeValue } from "../types/booking";
import { buildReferencePricePresentation } from "../utils/referencePrice";

type ReferencePriceRangeProps = {
  audience: "provider" | "customer";
  range?: ReferencePriceRangeValue | null;
};

export function ReferencePriceRange({
  audience,
  range,
}: ReferencePriceRangeProps) {
  const presentation = buildReferencePricePresentation(range, audience);
  if (audience === "provider" && presentation.value == null) {
    return null;
  }

  return (
    <View style={styles.card}>
      <Text style={styles.label}>{presentation.label}</Text>
      {presentation.value ? (
        <Text style={styles.value}>{presentation.value}</Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    gap: spacing.xs,
    padding: spacing.md,
  },
  label: {
    color: colors.mutedText,
    fontSize: 13,
    fontWeight: "700",
  },
  value: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
  },
});
