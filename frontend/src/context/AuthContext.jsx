import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi, getCurrentUserWithRefresh } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("checking"); // checking | authenticated | anonymous | select_role

  useEffect(() => {
    getCurrentUserWithRefresh()
      .then((body) => {
        const u = body.data;
        const isDualRoleDev = u.email === "080bct050.nischal@pcampus.edu.np" || u.email === "080bct077.sarthak@pcampus.edu.np";
        const savedDevRole = sessionStorage.getItem("devRole");
        if (import.meta.env.DEV && isDualRoleDev && savedDevRole && (savedDevRole === "admin" || savedDevRole === "student" || savedDevRole === "faculty")) {
          u.role = savedDevRole;
        }
        setUser(u);
        setStatus("authenticated");
      })
      .catch(() => setStatus("anonymous"));
  }, []);

  const loginWithGoogle = useCallback(async (idToken) => {
    const body = await authApi.loginWithGoogle(idToken);
    const u = body.data;
    setUser(u);
    
    const isDualRoleDev = u.email === "080bct050.nischal@pcampus.edu.np" || u.email === "080bct077.sarthak@pcampus.edu.np";
    if (import.meta.env.DEV && isDualRoleDev) {
      setStatus("select_role");
    } else {
      setStatus("authenticated");
    }
  }, []);

  const selectRole = useCallback((role) => {
    sessionStorage.setItem("devRole", role);
    setUser((prev) => prev ? { ...prev, role } : null);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout().finally(() => {
      sessionStorage.removeItem("devRole");
      setUser(null);
      setStatus("anonymous");
    });
  }, []);

  return (
    <AuthContext.Provider value={{ user, status, loginWithGoogle, selectRole, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);