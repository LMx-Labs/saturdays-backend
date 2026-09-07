import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { authClient } from "../api/client";
import { authApi } from "../api/modules";
import type { User } from "../api/types";
import { roleHome } from "../app/routing";

type AuthState = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  registerCustomer: (email: string, password: string) => Promise<User>;
  acceptInvitation: (token: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export { roleHome };

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void (async () => {
      if (authClient.hasRefreshToken() && await authClient.refresh()) {
        try {
          const current = await authApi.me();
          if (active) setUser(current);
        } catch {
          authClient.clear();
        }
      }
      if (active) setLoading(false);
    })();
    return () => { active = false; };
  }, []);

  const authenticate = useCallback(async (
    mode: "login" | "register",
    email: string,
    password: string,
  ) => {
    const tokens = await authClient.authenticate(mode, {
      email,
      password,
      ...(mode === "register" ? { role: "Customer" } : {}),
    });
    const nextUser = tokens.user ?? await authApi.me();
    setUser(nextUser);
    return nextUser;
  }, []);

  const value = useMemo<AuthState>(() => ({
    user,
    loading,
    login: (email, password) => authenticate("login", email, password),
    registerCustomer: (email, password) => authenticate("register", email, password),
    acceptInvitation: async (token, password) => {
      const tokens = await authClient.acceptInvitation(token, password);
      const nextUser = tokens.user ?? await authApi.me();
      setUser(nextUser);
      return nextUser;
    },
    logout: async () => {
      await authClient.logout();
      setUser(null);
    },
    logoutAll: async () => {
      await authClient.logout(true);
      setUser(null);
    },
  }), [authenticate, loading, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
