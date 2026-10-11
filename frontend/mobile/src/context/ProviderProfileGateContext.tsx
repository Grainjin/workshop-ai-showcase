import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";

import { getProviderSubmerchant } from "../api/marketplace";
import { getProviderVerificationStatus } from "../api/provider";
import { useAuth } from "./AuthContext";

const STEP_LABELS = {
  identity: "ID verification",
  qualification: "Service verification",
  payout: "Payout account",
} as const;

type ProviderOnboardingStep = keyof typeof STEP_LABELS;

type ProviderProfileGateContextValue = {
  hasProviderProfile: boolean | null;
  incompleteProviderSteps: ProviderOnboardingStep[];
  isProviderProfileLoading: boolean;
  isProviderProfileRequired: boolean;
  refreshProviderProfileStatus: () => Promise<void>;
  showProviderProfileRequiredMessage: () => void;
};

const ProviderProfileGateContext =
  createContext<ProviderProfileGateContextValue | null>(null);

export function ProviderProfileGateProvider({
  children,
}: {
  children: ReactNode;
}) {
  const { user } = useAuth();
  const [hasProviderProfile, setHasProviderProfile] = useState<boolean | null>(
    user?.role === "provider" ? null : true,
  );
  const [incompleteProviderSteps, setIncompleteProviderSteps] = useState<
    ProviderOnboardingStep[]
  >([]);
  const [isProviderProfileLoading, setIsProviderProfileLoading] = useState(
    user?.role === "provider",
  );
  const [isRequiredMessageVisible, setIsRequiredMessageVisible] =
    useState(false);

  const refreshProviderProfileStatus = useCallback(async () => {
    if (user?.role !== "provider") {
      setHasProviderProfile(true);
      setIncompleteProviderSteps([]);
      setIsProviderProfileLoading(false);
      return;
    }

    try {
      const [verification, payoutAccount] = await Promise.all([
        getProviderVerificationStatus(),
        getProviderSubmerchant(),
      ]);
      const incompleteSteps: ProviderOnboardingStep[] = [];
      if (verification?.identity_status !== "approved") {
        incompleteSteps.push("identity");
      }
      if (verification?.qualification_status !== "approved") {
        incompleteSteps.push("qualification");
      }
      if (payoutAccount?.status !== "active") {
        incompleteSteps.push("payout");
      }
      setIncompleteProviderSteps(incompleteSteps);
      setHasProviderProfile(incompleteSteps.length === 0);
    } catch (error) {
      const status = (error as { response?: { status?: number } }).response
        ?.status;

      // A missing onboarding record is incomplete. Other failures keep the
      // last known decision so a transient request cannot unlock the provider.
      if (status === 404) {
        setHasProviderProfile(false);
        setIncompleteProviderSteps([
          "identity",
          "qualification",
          "payout",
        ]);
      } else {
        setHasProviderProfile((current) => current ?? false);
      }
    } finally {
      setIsProviderProfileLoading(false);
    }
  }, [user?.id, user?.role]);

  useEffect(() => {
    void refreshProviderProfileStatus();
  }, [refreshProviderProfileStatus]);

  const showProviderProfileRequiredMessage = useCallback(() => {
    if (isProviderProfileLoading) {
      return;
    }
    setIsRequiredMessageVisible(true);
  }, [isProviderProfileLoading]);

  const requiredMessage = incompleteProviderSteps.length > 0
    ? `Complete ${incompleteProviderSteps
        .map((step) => STEP_LABELS[step])
        .join(", ")} before using provider work tools. Continue from Home or Account → Verification.`
    : "Complete all provider verification steps before using provider work tools. Continue from Home or Account → Verification.";

  const value = useMemo(
    () => ({
      hasProviderProfile,
      incompleteProviderSteps,
      isProviderProfileLoading,
      isProviderProfileRequired:
        user?.role === "provider" &&
        !isProviderProfileLoading &&
        hasProviderProfile === false,
      refreshProviderProfileStatus,
      showProviderProfileRequiredMessage,
    }),
    [
      hasProviderProfile,
      incompleteProviderSteps,
      isProviderProfileLoading,
      refreshProviderProfileStatus,
      showProviderProfileRequiredMessage,
      user?.role,
    ],
  );

  return (
    <ProviderProfileGateContext.Provider value={value}>
      {children}
      <Modal
        animationType="fade"
        onRequestClose={() => setIsRequiredMessageVisible(false)}
        transparent
        visible={isRequiredMessageVisible}
      >
        <View style={styles.overlay}>
          <View style={styles.dialog}>
            <Text style={styles.dialogTitle}>Verification required</Text>
            <Text style={styles.dialogMessage}>
              {requiredMessage}
            </Text>
            <Pressable
              accessibilityRole="button"
              onPress={() => setIsRequiredMessageVisible(false)}
              style={({ pressed }) => [
                styles.dialogButton,
                pressed ? styles.dialogButtonPressed : null,
              ]}
            >
              <Text style={styles.dialogButtonText}>OK</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </ProviderProfileGateContext.Provider>
  );
}

export function useProviderProfileGate() {
  const value = useContext(ProviderProfileGateContext);

  if (!value) {
    throw new Error(
      "useProviderProfileGate must be used inside ProviderProfileGateProvider",
    );
  }

  return value;
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0, 0, 0, 0.28)",
    padding: 24,
  },
  dialog: {
    width: "100%",
    maxWidth: 420,
    borderRadius: 8,
    backgroundColor: "#FFFFFF",
    padding: 24,
    shadowColor: "#000000",
    shadowOpacity: 0.16,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  dialogTitle: {
    color: "#202123",
    fontSize: 18,
    fontWeight: "700",
  },
  dialogMessage: {
    color: "#6E6E80",
    fontSize: 15,
    lineHeight: 22,
    marginTop: 10,
  },
  dialogButton: {
    alignItems: "center",
    justifyContent: "center",
    minHeight: 44,
    marginTop: 20,
    borderRadius: 8,
    backgroundColor: "#10A37F",
  },
  dialogButtonPressed: {
    backgroundColor: "#0E8F70",
  },
  dialogButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
});
