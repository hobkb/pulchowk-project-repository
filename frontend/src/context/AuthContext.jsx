import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi, getCurrentUserWithRefresh } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("checking"); // checking | authenticated | anonymous

  useEffect(() => {
    getCurrentUserWithRefresh()
      .then((body) => { setUser(body.data); setStatus("authenticated"); })
      .catch(() => setStatus("anonymous"));
  }, []);

  const loginWithGoogle = useCallback(async (idToken) => {
    const body = await authApi.loginWithGoogle(idToken);
    setUser(body.data);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout().finally(() => { setUser(null); setStatus("anonymous"); });
  }, []);

  return (
    <AuthContext.Provider value={{ user, status, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);