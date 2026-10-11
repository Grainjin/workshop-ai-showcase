import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { apiClient } from "../api/client";
import { DEMO_MODE } from "../config/env";
import { colors, spacing } from "../theme/theme";

export function ServiceStatusBanner() {
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!DEMO_MODE) return;
    let active = true;
    const controller = new AbortController();

    async function checkReadiness() {
      try {
        const response = await apiClient.get("/ready", {
          timeout: 5000,
          signal: controller.signal,
          validateStatus: status => status === 200 || status === 503,
        });
        if (!active) return;
        const data = response.data?.data;
        if (response.data?.success !== true || typeof data?.ready !== "boolean" ||
            typeof data?.ai_configured !== "boolean" ||
            !["available", "unavailable"].includes(data?.database)) {
          throw new Error("Invalid readiness response");
        }
        if (!data.ready || data.database === "unavailable") {
          setNotice("The service is temporarily unavailable. Please try again later.");
        } else if (!data.ai_configured) {
          setNotice("AI assistance is unavailable. You can still browse, book, and use simulated payments.");
        }
      } catch {
        if (active) setNotice("We could not check service availability. Please try again later.");
      }
    }

    void checkReadiness();
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  if (!notice) return null;

  return (
    <View role="status" accessibilityLiveRegion="polite" style={styles.banner}>
      <Text style={styles.text}>{notice}</Text>
      <Pressable accessibilityRole="button" accessibilityLabel="Dismiss service status"
        onPress={() => setNotice(null)} style={styles.dismiss}>
        <Text style={styles.dismissText}>Dismiss</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    backgroundColor: colors.surface,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
  },
  text: { flex: 1, color: colors.text, fontSize: 13 },
  dismiss: { padding: spacing.sm, minHeight: 44, justifyContent: "center" },
  dismissText: { color: colors.primaryPressed, fontSize: 13, fontWeight: "600" },
});
