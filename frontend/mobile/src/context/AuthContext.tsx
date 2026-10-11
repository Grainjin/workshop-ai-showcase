import AsyncStorage from "@react-native-async-storage/async-storage";
import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getCurrentUser,
  loginWithDemoRole,
  loginWithPassword,
  loginWithSocial,
  logoutByRefreshToken,
  patchCurrentUser,
  registerUser,
  updateCurrentUser,
  uploadCurrentUserAvatar,
} from "../api/auth";
import { setSessionHooks, setSessionTokens } from "../api/client";
import type {
  DemoRole,
  RegisterRequest,
  SocialLoginRequest,
  User,
  UserProfilePatchPayload,
} from "../types/auth";

const ACCESS_TOKEN_KEY = "workshop_ai_access_token";
const REFRESH_TOKEN_KEY = "workshop_ai_refresh_token";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signInDemo: (role: DemoRole) => Promise<void>;
  signUp: (payload: RegisterRequest) => Promise<void>;
  signInWithSocial: (payload: SocialLoginRequest) => Promise<void>;
  signOut: () => Promise<void>;
  updateUserProfile: (payload: { name: string }) => Promise<User>;
  patchUserProfile: (payload: UserProfilePatchPayload) => Promise<User>;
  /** The verify and change endpoints return the updated user. */
  setCurrentUser: (nextUser: User) => void;
  uploadAvatar: (payload: {
    uri: string;
    fileName?: string | null;
    mimeType?: string | null;
  }) => Promise<User>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setSessionHooks({
      onTokensRefreshed: async (nextAccessToken, nextRefreshToken, nextUser) => {
        setRefreshToken(nextRefreshToken);
        setUser(nextUser);
        await AsyncStorage.multiSet([
          [ACCESS_TOKEN_KEY, nextAccessToken],
          [REFRESH_TOKEN_KEY, nextRefreshToken],
        ]);
      },
      onSessionExpired: async () => {
        setRefreshToken(null);
        setUser(null);
        await AsyncStorage.multiRemove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY]);
      },
    });
    restoreSession();

    return () => {
      setSessionHooks(null);
    };
  }, []);

  async function saveSession(accessToken: string, newRefreshToken: string, nextUser: User) {
    setSessionTokens(accessToken, newRefreshToken);
    setRefreshToken(newRefreshToken);
    setUser(nextUser);
    await AsyncStorage.multiSet([
      [ACCESS_TOKEN_KEY, accessToken],
      [REFRESH_TOKEN_KEY, newRefreshToken],
    ]);
  }

  async function clearSession() {
    setSessionTokens(null, null);
    setRefreshToken(null);
    setUser(null);
    await AsyncStorage.multiRemove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY]);
  }

  async function restoreSession() {
    try {
      const [[, savedAccessToken], [, savedRefreshToken]] = await AsyncStorage.multiGet([
        ACCESS_TOKEN_KEY,
        REFRESH_TOKEN_KEY,
      ]);

      if (!savedAccessToken || !savedRefreshToken) {
        return;
      }

      setSessionTokens(savedAccessToken, savedRefreshToken);
      setRefreshToken(savedRefreshToken);
      const currentUser = await getCurrentUser();
      setUser(currentUser);
    } catch {
      await clearSession();
    } finally {
      setIsLoading(false);
    }
  }

  async function signIn(email: string, password: string) {
    const data = await loginWithPassword(email, password);
    await saveSession(data.access_token, data.refresh_token, data.user);
  }

  async function signInDemo(role: DemoRole) {
    const data = await loginWithDemoRole(role);
    await saveSession(data.access_token, data.refresh_token, data.user);
  }

  async function signUp(payload: RegisterRequest) {
    const data = await registerUser(payload);
    await saveSession(data.access_token, data.refresh_token, data.user);
  }

  async function signInWithSocial(payload: SocialLoginRequest) {
    const data = await loginWithSocial(payload);
    await saveSession(data.access_token, data.refresh_token, data.user);
  }

  async function signOut() {
    const tokenToRevoke = refreshToken;
    await clearSession();

    if (tokenToRevoke) {
      await logoutByRefreshToken(tokenToRevoke);
    }
  }

  async function updateUserProfile(payload: { name: string }) {
    const nextUser = await updateCurrentUser(payload);
    setUser(nextUser);

    return nextUser;
  }

  async function patchUserProfile(payload: UserProfilePatchPayload) {
    const nextUser = await patchCurrentUser(payload);
    setUser(nextUser);

    return nextUser;
  }

  async function uploadAvatar(payload: {
    uri: string;
    fileName?: string | null;
    mimeType?: string | null;
  }) {
    const data = await uploadCurrentUserAvatar(payload);
    setUser(data.user);

    return data.user;
  }

  function setCurrentUser(nextUser: User) {
    setUser(nextUser);
  }

  const value = useMemo(
    () => ({
      user,
      isLoading,
      signIn,
      signInDemo,
      signUp,
      signInWithSocial,
      signOut,
      updateUserProfile,
      patchUserProfile,
      setCurrentUser,
      uploadAvatar,
    }),
    [user, isLoading, refreshToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }

  return context;
}
