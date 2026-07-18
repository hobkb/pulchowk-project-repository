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
          onError(err.message || "Sign-in failed. Please try again.");
        }
      }}
      onError={() => onError("Google sign-in failed. Please try again.")}
      theme="filled_black"
      shape="pill"
    />
  );
}