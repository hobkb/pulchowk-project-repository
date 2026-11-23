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
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: './src/test/setup.js',
      // Only unit tests. The build output and node_modules are not test
      // material and scanning them makes a two-second run take much longer.
      include: ['src/**/*.test.{js,jsx}'],
    },
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
