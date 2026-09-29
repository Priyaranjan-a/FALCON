/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = process.env.FALCON_API ?? "http://127.0.0.1:8600";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    host: "127.0.0.1",
    port: 5180,
    strictPort: true,
    // Same-origin in development too: the session cookie is SameSite=Strict.
    proxy: { "/api": { target: api, changeOrigin: false } },
  },
  preview: { port: 5181, proxy: { "/api": { target: api } } },
  build: {
    target: "es2022",
    sourcemap: false,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        // Stable vendor chunks cache across releases; application code changes more often.
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (/[\/](react|react-dom|react-router|scheduler)[\/]/.test(id)) return "react";
          if (/[\/]d3-[a-z]+[\/]|[\/]internmap[\/]/.test(id)) return "viz";
          if (/[\/](@radix-ui|radix-ui|motion|motion-dom|motion-utils|framer-motion|cmdk|sonner)[\/]/.test(id)) return "ui";
          return "vendor";
        },
      },
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
