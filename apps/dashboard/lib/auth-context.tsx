"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Whole-app auth state (Sprint 9 §2.11) -- a plain Context, matching
 * RealtimeProvider's pattern rather than adding a state library for one
 * value. Mounted once in `Providers` so every page can read `user` without
 * re-fetching `/api/auth/me` itself. */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    api
      .getMe()
      .then((current) => {
        if (!cancelled) setUser(current);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // Fired by lib/api.ts on any 401, from any request anywhere in the app
    // -- a session that expired mid-visit is handled the same way as never
    // having been logged in: drop local state, bounce to /login.
    function onUnauthorized() {
      setUser(null);
      if (!window.location.pathname.startsWith("/login")) {
        router.push("/login");
      }
    }
    window.addEventListener("commander:unauthorized", onUnauthorized);
    return () => window.removeEventListener("commander:unauthorized", onUnauthorized);
  }, [router]);

  const login = useCallback(async (email: string, password: string) => {
    const current = await api.login(email, password);
    setUser(current);
  }, []);

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    const current = await api.register(email, password, displayName);
    setUser(current);
  }, []);

  const logout = useCallback(async () => {
    await api.logout().catch(() => {});
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
