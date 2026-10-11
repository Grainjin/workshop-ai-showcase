import { Platform } from "react-native";

const LOCAL_API_URL = "http://127.0.0.1:8000";
const LAN_API_URL = "http://10.0.2.2:8000";
const PUBLIC_DEPLOYMENT = process.env.EXPO_PUBLIC_PUBLIC_DEPLOYMENT === "true";

function requirePublicOrigin(value: string | undefined, protocol: string, name: string) {
  try {
    const url = new URL(value ?? "");
    if (
      url.protocol === protocol && url.hostname && !url.username && !url.password &&
      (url.pathname === "" || url.pathname === "/") && !url.search && !url.hash
    ) {
      return url.origin;
    }
  } catch {
    // Fixed diagnostic below: don't expose configuration values in the UI.
  }
  throw new Error(`Public deployment requires an explicit ${protocol} origin for ${name}`);
}

if (PUBLIC_DEPLOYMENT && process.env.EXPO_PUBLIC_DEMO_MODE !== "true") {
  throw new Error("Public deployment requires EXPO_PUBLIC_DEMO_MODE=true");
}

function isSameOrigin(value?: string) {
  return value === "same-origin";
}

function resolveApiBaseUrl() {
  const configured = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (PUBLIC_DEPLOYMENT) {
    return requirePublicOrigin(configured, "https:", "API");
  }
  if (isSameOrigin(configured)) {
    return "";
  }

  if (Platform.OS === "web") {
    return configured ?? LOCAL_API_URL;
  }

  return process.env.EXPO_PUBLIC_LAN_API_BASE_URL ?? LAN_API_URL;
}

function resolveWsBaseUrl() {
  const configured = process.env.EXPO_PUBLIC_WS_BASE_URL;
  if (PUBLIC_DEPLOYMENT) {
    return requirePublicOrigin(configured, "wss:", "WebSocket");
  }
  if (isSameOrigin(configured) || (!configured && API_BASE_URL === "")) {
    if (typeof window === "undefined") {
      return "";
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }

  if (configured) {
    return configured;
  }

  return API_BASE_URL.replace(/^http:\/\//, "ws://").replace(
    /^https:\/\//,
    "wss://",
  );
}

export const API_BASE_URL = resolveApiBaseUrl();

export const WS_BASE_URL = resolveWsBaseUrl();

// Build-time UI flag; the backend independently authorizes all demo operations.
export const DEMO_MODE: boolean = process.env.EXPO_PUBLIC_DEMO_MODE === "true";

// Google OAuth client IDs, one per platform, from Google Cloud Console. The
// backend accepts tokens for the same IDs (WORKSHOP_GOOGLE_CLIENT_IDS). The
// Google button only appears on a platform whose ID is set.
export const GOOGLE_CLIENT_IDS = {
  ios: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID || undefined,
  android: process.env.EXPO_PUBLIC_GOOGLE_ANDROID_CLIENT_ID || undefined,
  web: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID || undefined,
};
