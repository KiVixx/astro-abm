"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  claimGuestWorldlines,
  getAuthSession,
  loginAccount,
  logoutAccount,
  registerAccount,
} from "@/lib/api";
import type { CurrentUser, LoginRequest, RegisterRequest } from "@/lib/types";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  register: (payload: RegisterRequest) => Promise<number>;
  login: (payload: LoginRequest) => Promise<number>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const session = await getAuthSession();
      setUser(session.user || null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const claimGuest = useCallback(async () => {
    try {
      const result = await claimGuestWorldlines();
      return result.claimed_worldline_count;
    } catch {
      return 0;
    }
  }, []);

  const register = useCallback(async (payload: RegisterRequest) => {
    const session = await registerAccount(payload);
    setUser(session.user || null);
    return claimGuest();
  }, [claimGuest]);

  const login = useCallback(async (payload: LoginRequest) => {
    const session = await loginAccount(payload);
    setUser(session.user || null);
    return claimGuest();
  }, [claimGuest]);

  const logout = useCallback(async () => {
    await logoutAccount();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, register, login, logout, refresh }), [
    loading,
    login,
    logout,
    refresh,
    register,
    user,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
