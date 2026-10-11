import { Check } from "lucide-react-native";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "../theme/theme";

type LegalDocument = "terms" | "privacy";

type TermsCheckboxProps = {
  checked: boolean;
  onToggle: () => void;
  onOpenDocument: (document: LegalDocument) => void;
};

/** "I accept the Terms of Use and the Privacy Policy", with both links. */
export function TermsCheckbox({ checked, onToggle, onOpenDocument }: TermsCheckboxProps) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      onPress={onToggle}
      style={styles.row}
    >
      <View style={[styles.box, checked ? styles.boxChecked : null]}>
        {checked ? <Check color="#FFFFFF" size={14} /> : null}
      </View>
      <Text style={styles.text}>
        I accept the{" "}
        <Text
          accessibilityRole="link"
          onPress={() => onOpenDocument("terms")}
          style={styles.link}
        >
          Terms of Use
        </Text>{" "}
        and the{" "}
        <Text
          accessibilityRole="link"
          onPress={() => onOpenDocument("privacy")}
          style={styles.link}
        >
          Privacy Policy
        </Text>
        .
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
  },
  box: {
    width: 22,
    height: 22,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    marginTop: 1,
  },
  boxChecked: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  text: {
    color: colors.text,
    flex: 1,
    fontSize: 14,
    lineHeight: 20,
  },
  link: {
    color: colors.primary,
    fontWeight: "600",
    textDecorationLine: "underline",
  },
});
