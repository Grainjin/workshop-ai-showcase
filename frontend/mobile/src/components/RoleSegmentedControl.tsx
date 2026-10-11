import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "../theme/theme";
import type { RegisterRequest } from "../types/auth";

type RegisterRole = RegisterRequest["role"];

type RoleSegmentedControlProps = {
  value: RegisterRole;
  onChange: (value: RegisterRole) => void;
};

const options: Array<{ label: string; value: RegisterRole }> = [
  { label: "Customer", value: "customer" },
  { label: "Provider", value: "provider" },
];

export function RoleSegmentedControl({
  value,
  onChange,
}: RoleSegmentedControlProps) {
  return (
    <View style={styles.container}>
      {options.map((option) => {
        const isActive = option.value === value;

        return (
          <Pressable
            accessibilityRole="button"
            key={option.value}
            onPress={() => onChange(option.value)}
            style={[styles.option, isActive ? styles.optionActive : null]}
          >
            <Text style={[styles.label, isActive ? styles.labelActive : null]}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    gap: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    padding: spacing.xs,
  },
  option: {
    flex: 1,
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radius.sm,
  },
  optionActive: {
    backgroundColor: colors.background,
  },
  label: {
    color: colors.mutedText,
    fontSize: 15,
    fontWeight: "600",
  },
  labelActive: {
    color: colors.text,
  },
});
