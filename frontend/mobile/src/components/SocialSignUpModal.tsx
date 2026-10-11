import { useEffect, useState } from "react";
import { Modal, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "../theme/theme";
import type { RegisterRequest, SocialProvider } from "../types/auth";
import { PrimaryButton } from "./PrimaryButton";
import { RoleSegmentedControl } from "./RoleSegmentedControl";
import { SecondaryButton } from "./SecondaryButton";
import { TermsCheckbox } from "./TermsCheckbox";

type Role = RegisterRequest["role"];

type SocialSignUpModalProps = {
  visible: boolean;
  provider: SocialProvider;
  isSubmitting?: boolean;
  errorMessage?: string;
  onCancel: () => void;
  onOpenDocument: (document: "terms" | "privacy") => void;
  onSubmit: (role: Role) => void;
};

const PROVIDER_LABEL: Record<SocialProvider, string> = {
  apple: "Apple",
  google: "Google",
};

/**
 * Shown when a Google or Apple sign-in has no account yet. The provider
 * already proved the email and gave the name, so only the role and the Terms
 * are left; the same sign-in is then sent again to create the account.
 */
export function SocialSignUpModal({
  visible,
  provider,
  isSubmitting = false,
  errorMessage = "",
  onCancel,
  onOpenDocument,
  onSubmit,
}: SocialSignUpModalProps) {
  const [role, setRole] = useState<Role>("customer");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    if (visible) {
      setLocalError("");
    }
  }, [visible]);

  function handleSubmit() {
    if (!termsAccepted) {
      setLocalError("Please accept the Terms of Use to continue.");
      return;
    }
    setLocalError("");
    onSubmit(role);
  }

  const shownError = localError || errorMessage;

  return (
    <Modal animationType="fade" onRequestClose={onCancel} transparent visible={visible}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.title}>Finish signing up</Text>
          <Text style={styles.description}>
            There is no Workshop AI account for this {PROVIDER_LABEL[provider]} ID yet.
            Choose how you will use the app to create one.
          </Text>

          <View style={styles.roleBlock}>
            <Text style={styles.label}>Role</Text>
            <RoleSegmentedControl onChange={setRole} value={role} />
          </View>

          <TermsCheckbox
            checked={termsAccepted}
            onOpenDocument={onOpenDocument}
            onToggle={() => setTermsAccepted((accepted) => !accepted)}
          />

          {shownError ? <Text style={styles.error}>{shownError}</Text> : null}

          <View style={styles.actions}>
            <PrimaryButton
              isLoading={isSubmitting}
              label="Create account"
              onPress={handleSubmit}
            />
            <SecondaryButton disabled={isSubmitting} label="Cancel" onPress={onCancel} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0,0,0,0.45)",
    padding: spacing.lg,
  },
  sheet: {
    width: "100%",
    maxWidth: 420,
    gap: spacing.md,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  title: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "700",
  },
  description: {
    color: colors.mutedText,
    fontSize: 14,
    lineHeight: 20,
  },
  roleBlock: {
    gap: spacing.sm,
  },
  label: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
  error: {
    color: colors.danger,
    fontSize: 14,
    lineHeight: 20,
  },
  actions: {
    gap: spacing.sm,
  },
});
