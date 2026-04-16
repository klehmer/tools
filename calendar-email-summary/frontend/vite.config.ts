import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/auth": "http://localhost:8001",
      "/config": "http://localhost:8001",
      "/summary": "http://localhost:8001",
      "/jobs": "http://localhost:8001",
      "/reports": "http://localhost:8001",
      "/checklist": "http://localhost:8001",
      "/slack": "http://localhost:8001",
      "/analytics": "http://localhost:8001",
    },
  },
});
