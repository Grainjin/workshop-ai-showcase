import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { sendEmailCode, verifyEmail } from "../api/auth";
import { PrimaryButton } from "../components/PrimaryButton";
import { ScreenContainer } from "../components/ScreenContainer";
import { SecondaryButton } from "../components/SecondaryButton";
import { TextField } from "../components/TextField";
import { EMAIL_CODE_HINT } from "../components/VerifyCodeModal";
import { useAuth } from "../context/AuthContext";
import { colors, radius, spacing } from "../theme/theme";
import { getErrorMessage } from "../utils/errors";

const SIX_DIGITS = /^\d{6}$/;
const DEFAULT_RESEND_SECONDS = 60;

/**
 * Sign-up now proves the email before the account exists, so this screen is
 * for accounts created before that: customers and providers must confirm
 * their email before the rest of the app opens, and the backend refuses their
 * other endpoints until they do. A code is mailed as soon as this screen
 * opens. Verifying swaps in the main app.
 */
export function VerifyEmailScreen() {
  const { user, setCurrentUser, signOut } = useAuth();
  const [code, setCode] = useState("");
  const [resendIn, setResendIn] = useState(0);
  const [isSending, setIsSending] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [notice, setNotice] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const hasSentFirstCode = useRef(false);
  // No header here either, so stay clear of the status bar and home indicator.
  const insets = useSafeAreaInsets();

  async function sendCode() {
    setIsSending(true);
    setErrorMessage("");
    try {
      const sent = await sendEmailCode("verify_email");
      setNotice(`We sent a 6-digit code to ${sent.sent_to}.`);
      setResendIn(sent.resend_after_seconds);
      setCode("");
    } catch (error) {
      // A 429 means a code went out moments ago and is still in the inbox.
      if (axios.isAxiosError(error) && error.response?.status === 429) {
        setNotice(`We already sent a code to ${user?.email ?? "your email"}.`);
        setResendIn(DEFAULT_RESEND_SECONDS);
      }
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsSending(false);
    }
  }

  useEffect(() => {
    if (hasSentFirstCode.current) {
      return;
    }
    hasSentFirstCode.current = true;
    // Send once per visit, even if the effect runs twice in development.
    void sendCode();
  }, []);

  useEffect(() => {
    if (resendIn <= 0) {
      return;
    }
    const timer = setTimeout(() => setResendIn((value) => value - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  async function handleVerify() {
    setIsVerifying(true);
    setErrorMessage("");
    try {
      const updated = await verifyEmail(code);
      setCurrentUser(updated);
    } catch (error) {
      setErrorMessage(getErrorMessage(error));
      setIsVerifying(false);
    }
  }

  return (
    <View
      style={[styles.screen, { paddingTop: insets.top, paddingBottom: insets.bottom }]}
    >
      <ScreenContainer contentStyle={styles.content}>
        <View style={styles.card}>
          <Text style={styles.title}>Verify your email</Text>
          <Text style={styles.description}>
            {notice || `Sending a code to ${user?.email ?? "your email"}...`}
          </Text>
          <Text style={styles.description}>
            Enter it below to finish setting up your account.
          </Text>

          <TextField
            keyboardType="number-pad"
            label="Verification code"
            maxLength={6}
            onChangeText={(value) => setCode(value.replace(/[^0-9]/g, ""))}
            placeholder="123456"
            value={code}
          />
          <Text style={styles.hint}>{EMAIL_CODE_HINT}</Text>

          {errorMessage ? <Text style={styles.error}>{errorMessage}</Text> : null}

          <View style={styles.actions}>
            <PrimaryButton
              disabled={!SIX_DIGITS.test(code)}
              isLoading={isVerifying}
              label="Verify email"
              onPress={() => void handleVerify()}
            />
            <SecondaryButton
              disabled={resendIn > 0 || isSending}
              label={
                isSending
                  ? "Sending..."
                  : resendIn > 0
                    ? `Resend code (${resendIn}s)`
                    : "Resend code"
              }
              onPress={() => void sendCode()}
            />
            <SecondaryButton label="Sign out" onPress={() => void signOut()} />
          </View>
          <Text style={styles.hint}>
            Wrong address? Sign out and register again with the right email.
          </Text>
        </View>
      </ScreenContainer>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    alignItems: "center",
    justifyContent: "center",
  },
  card: {
    width: "100%",
    maxWidth: 420,
    gap: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.background,
    padding: spacing.lg,
  },
  title: {
    color: colors.text,
    fontSize: 24,
    fontWeight: "700",
  },
  description: {
    color: colors.mutedText,
    fontSize: 15,
    lineHeight: 21,
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
