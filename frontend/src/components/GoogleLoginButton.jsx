import { GoogleLogin } from "@react-oauth/google";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function GoogleLoginButton({ onError }) {
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  return (
    <GoogleLogin
      onSuccess={async (res) => {
        try {
          await loginWithGoogle(res.credential);
          navigate("/dashboard");
        } catch (err) {
          if (onError) {
            onError(err);
          } else {
            console.error("Login error:", err);
          }
        }
      }}
      onError={() => {
        if (onError) {
          onError(new Error("Google OAuth initialization failed"));
        } else {
          console.error("Google Login failed");
        }
      }}
      // Square and outlined, to match a system that has no pills in it
      // and sets its own controls as ink on paper.
      theme="outline"
      shape="rectangular"
      text="signin_with"
      logo_alignment="left"
      width="320"
    />
  );
}