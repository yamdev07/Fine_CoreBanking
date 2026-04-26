"use client";

import React, {
  createContext, useCallback, useContext, useEffect, useState,
} from "react";
import { useRouter } from "next/navigation";
import type { AuthUser } from "@/lib/auth";
import { clearAuth, loadAuth, saveAuth } from "@/lib/auth";
import { login as apiLogin } from "@/lib/api/auth";

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const state = loadAuth();
    if (state) {
      setToken(state.token);
      setUser(state.user);
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const data = await apiLogin(username, password);
    saveAuth(data.access_token, data.user, data.expires_in);
    setToken(data.access_token);
    setUser(data.user);
    router.push("/dashboard");
  }, [router]);

  const logout = useCallback(() => {
    clearAuth();
    setToken(null);
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useRequireAuth(): AuthContextValue {
  const auth = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!auth.loading && !auth.user) {
      router.push("/login");
    }
  }, [auth.loading, auth.user, router]);
  return auth;
}
