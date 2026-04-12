import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    proxy: {
      "/status": "http://localhost:8000",
      "/config": "http://localhost:8000",
      "/link": "http://localhost:8000",
      "/sources": "http://localhost:8000",
      "/sync": "http://localhost:8000",
      "/accounts": "http://localhost:8000",
      "/transactions": "http://localhost:8000",
      "/networth": "http://localhost:8000",
      "/subscriptions": "http://localhost:8000",
      "/income": "http://localhost:8000",
      "/dashboard": "http://localhost:8000",
      "/goals": "http://localhost:8000",
      "/plan": "http://localhost:8000",
    },
  },
});
