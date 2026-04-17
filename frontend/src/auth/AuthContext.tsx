import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiFetch } from "../api";
import type { User } from "../types";

type AuthState = {
  user: User | null;
  loading: boolean;
  token: string | null;
  setToken: (t: string | null) => void;
  refreshMe: () => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() =>
    localStorage.getItem("infragis_token"),
  );
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!token);

  const setToken = useCallback((t: string | null) => {
    setTokenState(t);
    if (t) localStorage.setItem("infragis_token", t);
    else localStorage.removeItem("infragis_token");
  }, []);

  const refreshMe = useCallback(async () => {
    const t = localStorage.getItem("infragis_token");
    if (!t) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const me = await apiFetch<User>("/auth/me");
      setUser(me);
    } catch {
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [setToken]);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe, token]);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, [setToken]);

  const value = useMemo(
    () => ({ user, loading, token, setToken, refreshMe, logout }),
    [user, loading, token, setToken, refreshMe, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
