import { Platform } from "react-native";

import { apiClient, setSessionTokens } from "./client";
import type {
  ApiResponse,
  DemoRole,
  RegisterRequest,
  SocialLoginRequest,
  SocialLoginResponse,
  TokenResponse,
  User,
  UserProfilePatchPayload,
} from "../types/auth";

function unwrapData<T>(response: { data: ApiResponse<T> }) {
  if (!response.data.success || !response.data.data) {
    throw new Error(response.data.message || "Request failed");
  }

  return response.data.data;
}

export async function loginWithPassword(email: string, password: string) {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const response = await apiClient.post<ApiResponse<TokenResponse>>(
    "/login",
    formData.toString(),
    {
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    },
  );
  const data = unwrapData(response);
  setSessionTokens(data.access_token, data.refresh_token);

  return data;
}

export async function loginWithDemoRole(role: DemoRole): Promise<TokenResponse> {
  const response = await apiClient.post<ApiResponse<TokenResponse>>(
    "/demo/login",
    { role },
  );
  const data = unwrapData(response);
  setSessionTokens(data.access_token, data.refresh_token);

  return data;
}

export async function registerUser(payload: RegisterRequest) {
  await apiClient.post("/register", payload);

  return loginWithPassword(payload.email, payload.password);
}

/**
 * Exchanges a Google or Apple ID token for a session. Fails with 409 when no
 * account exists yet and the Terms were not accepted.
 */
export async function loginWithSocial(payload: SocialLoginRequest) {
  const response = await apiClient.post<ApiResponse<SocialLoginResponse>>(
    "/social-login",
    payload,
  );
  const data = unwrapData(response);
  setSessionTokens(data.access_token, data.refresh_token);

  return data;
}

export async function refreshAccessToken(refreshToken: string) {
  const response = await apiClient.post<ApiResponse<TokenResponse>>("/refresh-token", {
    refresh_token: refreshToken,
  });
  const data = unwrapData(response);
  setSessionTokens(data.access_token, data.refresh_token);

  return data;
}

export async function getCurrentUser() {
  const response = await apiClient.get<ApiResponse<User>>("/me");

  return unwrapData(response);
}

export async function updateCurrentUser(payload: { name: string }) {
  const response = await apiClient.put<ApiResponse<User>>("/me", payload);

  return unwrapData(response);
}

export async function patchCurrentUser(payload: UserProfilePatchPayload) {
  const response = await apiClient.patch<ApiResponse<User>>("/me", payload);

  return unwrapData(response);
}

export async function uploadCurrentUserAvatar(payload: {
  uri: string;
  fileName?: string | null;
  mimeType?: string | null;
}) {
  const formData = new FormData();
  const fileName = payload.fileName || "avatar.jpg";
  const mimeType = payload.mimeType || "image/jpeg";

  if (Platform.OS === "web") {
    const fileResponse = await fetch(payload.uri);
    const blob = await fileResponse.blob();
    const file = new File([blob], fileName, {
      type: mimeType || blob.type || "image/jpeg",
    });

    formData.append("file", file);
  } else {
    formData.append("file", {
      uri: payload.uri,
      name: fileName,
      type: mimeType,
    } as unknown as Blob);
  }

  const response = await apiClient.post<
    ApiResponse<{
      original_file_name: string;
      file_name: string;
      file_url: string;
      content_type: string;
      size: number;
      user: User;
    }>
  >("/me/avatar", formData);

  return unwrapData(response);
}

export type EmailCodePurpose = "verify_email" | "change_email";

export type SendEmailCodeResult = {
  sent_to: string;
  expires_in_seconds: number;
  resend_after_seconds: number;
};

/**
 * Sign-up step one: mails a code to an address that has no account yet.
 * Fails with 429 while the resend wait runs.
 */
export async function sendRegisterEmailCode(email: string) {
  const response = await apiClient.post<ApiResponse<SendEmailCodeResult>>(
    "/register/email-code",
    { email },
  );

  return unwrapData(response);
}

/**
 * Mails a six-digit code. "verify_email" goes to the current address,
 * "change_email" to `newEmail`. Fails with 429 while the resend wait runs.
 */
export async function sendEmailCode(purpose: EmailCodePurpose, newEmail?: string) {
  const response = await apiClient.post<ApiResponse<SendEmailCodeResult>>(
    "/auth/email-code",
    newEmail === undefined ? { purpose } : { purpose, new_email: newEmail },
  );

  return unwrapData(response);
}

/** Checks the code mailed by sendEmailCode("verify_email"). */
export async function verifyEmail(code: string) {
  const response = await apiClient.post<ApiResponse<User>>("/auth/verify-email", {
    code,
  });

  return unwrapData(response);
}

/**
 * Still a demo: any six digits pass. Fails with a clear message when
 * the profile has no phone number.
 */
export async function verifyPhone(code: string) {
  const response = await apiClient.post<ApiResponse<User>>("/auth/verify-phone", {
    code,
  });

  return unwrapData(response);
}

/** The backend revokes every refresh token on success. */
export async function changePassword(payload: {
  currentPassword: string;
  newPassword: string;
}) {
  const response = await apiClient.post<ApiResponse<User>>("/auth/change-password", {
    current_password: payload.currentPassword,
    new_password: payload.newPassword,
  });

  return unwrapData(response);
}

/** Confirmed with the code mailed by sendEmailCode("change_email"). */
export async function changeEmail(payload: { newEmail: string; code: string }) {
  const response = await apiClient.post<ApiResponse<User>>("/auth/change-email", {
    new_email: payload.newEmail,
    code: payload.code,
  });

  return unwrapData(response);
}

export async function logoutByRefreshToken(refreshToken: string) {
  await apiClient.post("/logout", {
    refresh_token: refreshToken,
  });
  setSessionTokens(null, null);
}
