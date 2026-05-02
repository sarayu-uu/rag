/**
 * File overview: This frontend module defines part of the React UI flow for auth, ingestion, chat, dashboards, or admin operations.
 * It connects user interactions to API calls and renders role-aware experiences in the RAG workspace.
 */

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getMe, getStoredTokens, login, normalizeRole, setStoredTokens } from "../lib/api";

const AuthContext = createContext(null);

/**
 * Detailed function explanation:
 * - Purpose: `AuthProvider` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);

  /**
   * Detailed function explanation:
   * - Purpose: `hydrateUser` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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

  /**
   * Detailed function explanation:
   * - Purpose: `signIn` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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

  /**
   * Detailed function explanation:
   * - Purpose: `refreshProfile` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
  async function refreshProfile() {
    const response = await getMe();
    setUser({
      ...response.user,
      role: normalizeRole(response.user?.role),
    });
    return response.user;
  }

  /**
   * Detailed function explanation:
   * - Purpose: `signOut` handles a specific UI/data responsibility in this file.
   * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
   * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
   *   predictable UI output or data transformations used by the next step.
   */
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

/**
 * Detailed function explanation:
 * - Purpose: `useAuth` handles a specific UI/data responsibility in this file.
 * - Usage in flow: It is called by React rendering, event handlers, or API workflows for this feature.
 * - Input/Output intent: Receives props/state/input values, applies feature logic, and returns
 *   predictable UI output or data transformations used by the next step.
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
