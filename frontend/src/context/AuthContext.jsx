import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi, getCurrentUserWithRefresh, setOnSessionExpired } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("checking"); // checking | authenticated | onboarding | anonymous

  useEffect(() => {
    getCurrentUserWithRefresh()
      .then((body) => {
        const u = body.data;
        setUser(u);
        if (!u.is_onboarded) {
          setStatus("onboarding");
        } else {
          setStatus("authenticated");
        }
      })
      .catch(() => setStatus("anonymous"));
  }, []);

  // If a token refresh ever fails mid-session (e.g. the refresh token
  // itself has expired), any in-flight authenticated request reports it
  // here so the app drops back to signed-out instead of leaving the user
  // stuck on a page whose requests will keep failing.
  useEffect(() => {
    setOnSessionExpired(() => {
      setUser(null);
      setStatus("anonymous");
    });
    return () => setOnSessionExpired(null);
  }, []);

  const loginWithGoogle = useCallback(async (idToken) => {
    const body = await authApi.loginWithGoogle(idToken);
    const u = body.data;
    setUser(u);
    
    if (!u.is_onboarded) {
      setStatus("onboarding");
    } else {
      setStatus("authenticated");
    }
  }, []);

  const completeProfile = useCallback(async (formData) => {
    const body = await authApi.completeProfile(formData);
    const u = body.data;
    setUser(u);
    setStatus("authenticated");
    return u;
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout().finally(() => {
      setUser(null);
      setStatus("anonymous");
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, status, loginWithGoogle, completeProfile, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);