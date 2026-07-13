import { GoogleLogin } from "@react-oauth/google";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function GoogleLoginButton() {
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  return (
    <GoogleLogin
      onSuccess={async (res) => {
        await loginWithGoogle(res.credential);
        navigate("/dashboard");
      }}
      onError={() => alert("Sign-in failed")}
      theme="filled_black"
      shape="pill"
    />
  );
}