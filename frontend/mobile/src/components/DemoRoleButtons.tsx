import { useEffect, useReducer, useRef } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

import { DEMO_MODE } from "../config/env";
import { createDemoLoginState, getDemoRoleButtons, reduceDemoLogin } from "../features/demo/demo-state";
import { colors, radius, spacing } from "../theme/theme";
import type { DemoRole } from "../types/auth";

export function DemoRoleButtons({ onSignIn }: {
  onSignIn: (role: DemoRole) => Promise<void>;
}) {
  const [state, dispatch] = useReducer(reduceDemoLogin, undefined, createDemoLoginState);
  const requestInFlight = useRef(false);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  async function handleSignIn(role: DemoRole) {
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    dispatch({ type: "start", role });
    try {
      await onSignIn(role);
      if (isMounted.current) dispatch({ type: "success" });
    } catch {
      if (isMounted.current) dispatch({ type: "failure" });
    } finally {
      requestInFlight.current = false;
    }
  }

  if (!DEMO_MODE) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Choose a demo role</Text>
      {getDemoRoleButtons(DEMO_MODE, state).map((button) => (
        <Pressable
          key={button.role}
          accessibilityLabel={button.accessibilityLabel}
          accessibilityRole="button"
          accessibilityState={{ disabled: button.disabled, busy: button.isLoading }}
          disabled={button.disabled}
          onPress={() => void handleSignIn(button.role)}
          style={({ pressed }) => [
            styles.button,
            pressed && !button.disabled ? styles.pressed : null,
            button.disabled ? styles.disabled : null,
          ]}
        >
          <View style={styles.buttonContent}>
            <Text style={styles.label}>{button.label}</Text>
            <Text style={styles.purpose}>{button.purpose}</Text>
          </View>
          {button.isLoading ? <ActivityIndicator color={colors.primary} /> : null}
        </Pressable>
      ))}
      {state.errorMessage ? (
        <Text accessibilityRole="alert" accessibilityLiveRegion="polite" style={styles.error}>
          {state.errorMessage}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: spacing.md },
  heading: { color: colors.text, fontSize: 18, fontWeight: "700" },
  button: {
    minHeight: 72,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.md,
  },
  buttonContent: { flex: 1, gap: spacing.xs },
  label: { color: colors.primary, fontSize: 16, fontWeight: "700" },
  purpose: { color: colors.mutedText, fontSize: 13, lineHeight: 18 },
  pressed: { backgroundColor: colors.surface },
  disabled: { opacity: 0.55 },
  error: { color: colors.danger, fontSize: 14, lineHeight: 20 },
});
