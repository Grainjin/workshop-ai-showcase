import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { API_BASE_URL } from "../config/env";
import type { ApiResponse, TokenResponse, User } from "../types/auth";

type RetryConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

type SessionHooks = {
  onTokensRefreshed: (
    accessToken: string,
    refreshToken: string,
    user: User,
  ) => void | Promise<void>;
  onSessionExpired: () => void | Promise<void>;
};

let accessToken: string | null = null;
let refreshToken: string | null = null;
let sessionHooks: SessionHooks | null = null;
let refreshInFlight: Promise<boolean> | null = null;

const AUTH_PATHS_WITHOUT_REFRESH = new Set([
  "/demo/login",
  "/login",
  "/register",
  "/register/email-code",
  "/token",
  "/refresh-token",
  "/logout",
  "/social-login",
]);

// All HTTP requests go through here for auth, error handling, and response unwrapping.
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;
    if (
      error.response?.status !== 401 ||
      !original ||
      original._retry ||
      shouldSkipRefresh(original.url) ||
      !refreshToken
    ) {
      return Promise.reject(error);
    }

    original._retry = true;
    const refreshed = await refreshSessionOnce();
    if (!refreshed) {
      return Promise.reject(error);
    }

    original.headers = original.headers ?? {};
    original.headers.Authorization = `Bearer ${accessToken}`;
    return apiClient(original);
  },
);

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setRefreshToken(token: string | null) {
  refreshToken = token;
}

export function setSessionTokens(
  nextAccessToken: string | null,
  nextRefreshToken: string | null,
) {
  accessToken = nextAccessToken;
  refreshToken = nextRefreshToken;
}

export function getAccessToken() {
  return accessToken;
}

export function setSessionHooks(hooks: SessionHooks | null) {
  sessionHooks = hooks;
}

function shouldSkipRefresh(url?: string) {
  if (!url) {
    return false;
  }

  try {
    const path = new URL(url, "http://local.invalid").pathname;
    return AUTH_PATHS_WITHOUT_REFRESH.has(path);
  } catch {
    return AUTH_PATHS_WITHOUT_REFRESH.has(url.split("?")[0]);
  }
}

function refreshSessionOnce() {
  if (!refreshInFlight) {
    refreshInFlight = refreshSession().finally(() => {
      refreshInFlight = null;
    });
  }

  return refreshInFlight;
}

async function refreshSession() {
  const currentRefreshToken = refreshToken;
  if (!currentRefreshToken) {
    return false;
  }

  try {
    const response = await axios.post<ApiResponse<TokenResponse>>(
      `${API_BASE_URL}/refresh-token`,
      { refresh_token: currentRefreshToken },
      { timeout: 15000 },
    );
    const tokens = response.data.data;
    if (!response.data.success || !tokens?.access_token || !tokens.refresh_token) {
      await expireSession();
      return false;
    }

    setSessionTokens(tokens.access_token, tokens.refresh_token);
    await sessionHooks?.onTokensRefreshed(
      tokens.access_token,
      tokens.refresh_token,
      tokens.user,
    );
    return true;
  } catch {
    await expireSession();
    return false;
  }
}

async function expireSession() {
  setSessionTokens(null, null);
  await sessionHooks?.onSessionExpired();
}
