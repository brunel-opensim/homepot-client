import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";
import { buildInfoPlugin } from "./build-info-plugin.js";

export default defineConfig({
  plugins: [react(), buildInfoPlugin()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
  },
});
