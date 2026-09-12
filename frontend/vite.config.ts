import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // In dev, tutte le chiamate /api/* vengono proxate al backend FastAPI
      "/api": {
        target: "http://localhost:8000",
        // Nessun rewrite: il backend ora serve /api/* anche in dev
        changeOrigin: true,
      },
      // Asset statici serviti direttamente da FastAPI
      "/assets": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
