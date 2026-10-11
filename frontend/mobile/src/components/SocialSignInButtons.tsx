import * as AppleAuthentication from "expo-apple-authentication";
import * as Google from "expo-auth-session/providers/google";
import * as Crypto from "expo-crypto";
import * as WebBrowser from "expo-web-browser";
import { useEffect, useRef, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { GOOGLE_CLIENT_IDS } from "../config/env";
import { colors, radius, spacing } from "../theme/theme";
import type { SocialProvider } from "../types/auth";

// Closes the Google popup on web once it redirects back.
WebBrowser.maybeCompleteAuthSession();

export type SocialCredential = {
  provider: SocialProvider;
  idToken: string;
  /** The raw nonce; the provider only saw it (Apple: its SHA-256) in the token request. */
  nonce: string;
  firstName?: string;
  lastName?: string;
};

type SocialSignInButtonsProps = {
  onCredential: (credential: SocialCredential) => void;
  onError: (message: string) => void;
  disabled?: boolean;
};

// Both buttons share Apple's white-outline look so they read as a pair.
const BUTTON_HEIGHT = 46;

const GOOGLE_CLIENT_ID_FOR_PLATFORM = Platform.select({
  ios: GOOGLE_CLIENT_IDS.ios,
  android: GOOGLE_CLIENT_IDS.android,
  default: GOOGLE_CLIENT_IDS.web,
});

export function SocialSignInButtons(props: SocialSignInButtonsProps) {
  const [appleAvailable, setAppleAvailable] = useState(false);

  useEffect(() => {
    // Sign in with Apple is native to iOS only.
    if (Platform.OS !== "ios") {
      return;
    }
    AppleAuthentication.isAvailableAsync()
      .then(setAppleAvailable)
      .catch(() => setAppleAvailable(false));
  }, []);

  const googleReady = Boolean(GOOGLE_CLIENT_ID_FOR_PLATFORM);

  if (!googleReady && !appleAvailable) {
    return __DEV__ ? (
      <Text style={styles.hint}>
        Google and Apple sign-in are not set up for this build.
      </Text>
    ) : null;
  }

  return (
    <View style={styles.buttons}>
      {/* The Google hook throws without a client ID, so it only mounts when one is set. */}
      {googleReady ? <GoogleButton {...props} /> : null}
      {appleAvailable ? <AppleButton {...props} /> : null}
    </View>
  );
}

function GoogleButton({ onCredential, onError, disabled }: SocialSignInButtonsProps) {
  const nonceRef = useRef(Crypto.randomUUID());
  const [request, response, promptAsync] = Google.useIdTokenAuthRequest({
    iosClientId: GOOGLE_CLIENT_IDS.ios,
    androidClientId: GOOGLE_CLIENT_IDS.android,
    webClientId: GOOGLE_CLIENT_IDS.web,
    selectAccount: true,
    extraParams: { nonce: nonceRef.current },
  });

  useEffect(() => {
    if (response?.type === "success") {
      const idToken = response.params.id_token;
      if (idToken) {
        onCredential({ provider: "google", idToken, nonce: nonceRef.current });
      } else {
        onError("Google did not return an ID token. Try again.");
      }
    } else if (response?.type === "error") {
      onError(response.error?.message || "Google sign-in failed. Try again.");
    }
    // "cancel" and "dismiss" mean the user closed the sheet; nothing to say.
  }, [response]);

  const isDisabled = disabled || !request;

  return (
    <Pressable
      accessibilityLabel="Continue with Google"
      accessibilityRole="button"
      disabled={isDisabled}
      onPress={() => {
        // On web the Google page opens in a popup, which the browser may block.
        promptAsync().catch(() =>
          onError("Could not open Google sign-in. Allow pop-ups for this site and try again."),
        );
      }}
      style={({ pressed }) => [
        styles.googleButton,
        pressed && !isDisabled ? styles.googleButtonPressed : null,
        isDisabled ? styles.disabled : null,
      ]}
    >
      <GoogleLogo />
      <Text style={styles.googleLabel}>Continue with Google</Text>
    </Pressable>
  );
}

/** The standard multicolour "G" from Google's sign-in branding guidelines. */
function GoogleLogo() {
  return (
    <Svg height={18} viewBox="0 0 48 48" width={18}>
      <Path
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
        fill="#EA4335"
      />
      <Path
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
        fill="#4285F4"
      />
      <Path
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
        fill="#FBBC05"
      />
      <Path
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
        fill="#34A853"
      />
    </Svg>
  );
}

function AppleButton({ onCredential, onError, disabled }: SocialSignInButtonsProps) {
  async function signIn() {
    if (disabled) {
      return;
    }

    // Apple gets the hash; the backend hashes the raw nonce to compare.
    const nonce = Crypto.randomUUID();
    const hashedNonce = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      nonce,
    );

    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
        nonce: hashedNonce,
      });

      if (!credential.identityToken) {
        onError("Apple did not return an identity token. Try again.");
        return;
      }

      onCredential({
        provider: "apple",
        idToken: credential.identityToken,
        nonce,
        firstName: credential.fullName?.givenName ?? undefined,
        lastName: credential.fullName?.familyName ?? undefined,
      });
    } catch (error) {
      const { code, message } = error as { code?: string; message?: string };
      if (code === "ERR_REQUEST_CANCELED") {
        return;
      }
      console.warn("Apple sign-in failed", code, message);
      onError(`Apple sign-in failed (${code ?? "unknown error"}). Try again.`);
    }
  }

  return (
    <AppleAuthentication.AppleAuthenticationButton
      buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.WHITE_OUTLINE}
      buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
      cornerRadius={radius.md}
      onPress={() => void signIn()}
      style={[styles.appleButton, disabled ? styles.disabled : null]}
    />
  );
}

const styles = StyleSheet.create({
  buttons: {
    gap: spacing.sm,
  },
  appleButton: {
    width: "100%",
    height: BUTTON_HEIGHT,
  },
  googleButton: {
    height: BUTTON_HEIGHT,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    // Matches the hairline-ish outline Apple draws on its own button.
    borderWidth: 0.67,
    borderColor: "#000000",
    borderRadius: radius.md,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: spacing.md,
  },
  googleButtonPressed: {
    backgroundColor: colors.surface,
  },
  googleLabel: {
    color: "#000000",
    // Sized to Apple's button text at this height (measured on device).
    fontSize: 18,
    fontWeight: "500",
  },
  disabled: {
    opacity: 0.55,
  },
  hint: {
    color: colors.mutedText,
    fontSize: 13,
    lineHeight: 18,
    textAlign: "center",
  },
});
