import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getMe, getStoredTokens, login, normalizeRole, setStoredTokens } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  async function hydrateUser() {
    const tokens = getStoredTokens();
    if (!tokens.accessToken) {
      setUser(null);
      setBooting(false);
      return;
    }

    try {
      const response = await getMe();
      setUser({
        ...response.user,
        role: normalizeRole(response.user?.role),
      });
    } catch {
      setStoredTokens(null);
      setUser(null);
    } finally {
      setBooting(false);
    }
  }

  useEffect(() => {
    hydrateUser();
  }, []);

  async function signIn(credentials) {
    const response = await login(credentials);
    setStoredTokens({
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
    });
    setUser({
      ...response.user,
      role: normalizeRole(response.user?.role),
    });
    return response;
  }

  async function refreshProfile() {
    const response = await getMe();
    setUser({
      ...response.user,
      role: normalizeRole(response.user?.role),
    });
    return response.user;
  }

  function signOut() {
    setStoredTokens(null);
    setUser(null);
  }

  const value = useMemo(
    () => ({
      user,
      booting,
      isAuthenticated: Boolean(user),
      signIn,
      signOut,
      refreshProfile,
    }),
    [user, booting]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
