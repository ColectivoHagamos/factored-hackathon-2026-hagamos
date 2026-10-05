import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The API serves the built files (ADR 0006); in development, Vite forwards /v1 to a local API.
export default defineConfig({
  plugins: [tanstackRouter({ target: "react", autoCodeSplitting: true }), react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { proxy: { "/v1": "http://127.0.0.1:8000" } },
  // No asset becomes a data: URI: the Content-Security-Policy allows only files from the same origin.
  build: { outDir: "dist", assetsInlineLimit: 0, sourcemap: false },
  // West of Greenwich, as the customers are: a date read as UTC would show the day before.
  test: { environment: "node", include: ["src/**/*.test.ts"], env: { TZ: "America/Bogota" } },
});
