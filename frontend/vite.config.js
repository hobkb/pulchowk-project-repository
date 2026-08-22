import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  // Determine backend target URL dynamically from environment variables
  let backendTarget = env.VITE_BACKEND_URL;
  if (!backendTarget && env.VITE_API_BASE_URL) {
    backendTarget = env.VITE_API_BASE_URL.replace(/\/api\/?$/, '');
  }
  if (!backendTarget) {
    backendTarget = 'http://localhost:8000';
  }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/media': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
