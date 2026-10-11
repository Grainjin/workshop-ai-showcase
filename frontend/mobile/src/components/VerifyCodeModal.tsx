import { useEffect, useState } from "react";
import { Modal, StyleSheet, Text, View } from "react-native";

import { colors, radius, spacing } from "../theme/theme";
import { PrimaryButton } from "./PrimaryButton";
import { SecondaryButton } from "./SecondaryButton";
import { TextField } from "./TextField";

/**
 * The shared six-digit verification step, used by email and phone
 * verification and by the change-email flow.
 *
 * Email codes are mailed by the backend; pass `onResend` to offer a new one
 * once the resend wait is over. Phone verification is still a demo.
 */
export const PHONE_CODE_HINT = "Phone verification is a demo: enter any 6 digits.";
export const EMAIL_CODE_HINT =
  "Check your inbox and spam folder. The code expires in 10 minutes.";

const SIX_DIGITS = /^\d{6}$/;

type VerifyCodeModalProps = {
  visible: boolean;
  title: string;
  description: string;
  isSubmitting?: boolean;
  errorMessage?: string;
  hint: string;
  /** Seconds before "Resend code" unlocks, counted from when the modal opens. */
  resendAfterSeconds?: number;
  onResend?: () => Promise<void>;
  onCancel: () => void;
  onSubmit: (code: string) => void;
};

export function VerifyCodeModal({
  visible,
  title,
  description,
  isSubmitting = false,
  errorMessage = "",
  hint,
  resendAfterSeconds = 0,
  onResend,
  onCancel,
  onSubmit,
}: VerifyCodeModalProps) {
  const [code, setCode] = useState("");
  const [resendIn, setResendIn] = useState(0);
  const [isResending, setIsResending] = useState(false);

  // Reopening the modal should never show the previous attempt. A code was
  // just sent, so the resend wait starts again too.
  useEffect(() => {
    if (visible) {
      setCode("");
      setResendIn(resendAfterSeconds);
    }
  }, [visible, resendAfterSeconds]);

  useEffect(() => {
    if (!visible || resendIn <= 0) {
      return;
    }
    const timer = setTimeout(() => setResendIn((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [visible, resendIn]);

  async function handleResend() {
    if (!onResend) {
      return;
    }
    setIsResending(true);
    try {
      await onResend();
      setCode("");
      setResendIn(resendAfterSeconds);
    } catch {
      // The parent shows the reason through errorMessage.
    } finally {
      setIsResending(false);
    }
  }

  const isComplete = SIX_DIGITS.test(code);

  return (
    <Modal
      animationType="fade"
      onRequestClose={onCancel}
      transparent
      visible={visible}
    >
      <View style={styles.backdrop}>
        <View accessibilityViewIsModal style={styles.sheet}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.description}>{description}</Text>

          <TextField
            keyboardType="number-pad"
            label="Verification code"
            maxLength={6}
            onChangeText={(value) => setCode(value.replace(/[^0-9]/g, ""))}
            placeholder="123456"
            value={code}
          />
          <Text style={styles.hint}>{hint}</Text>

          {errorMessage ? (
            <Text style={styles.error}>{errorMessage}</Text>
          ) : null}

          <View style={styles.actions}>
            <PrimaryButton
              disabled={!isComplete}
              isLoading={isSubmitting}
              label="Confirm"
              onPress={() => onSubmit(code)}
            />
            {onResend ? (
              <SecondaryButton
                disabled={resendIn > 0 || isResending}
                label={
                  isResending
                    ? "Sending..."
                    : resendIn > 0
                      ? `Resend code (${resendIn}s)`
                      : "Resend code"
                }
                onPress={() => void handleResend()}
              />
            ) : null}
            <SecondaryButton label="Cancel" onPress={onCancel} />
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
    gap: spacing.sm,
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
  hint: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
  },
  error: {
    color: colors.danger,
    fontSize: 14,
    lineHeight: 20,
  },
  actions: {
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
});
