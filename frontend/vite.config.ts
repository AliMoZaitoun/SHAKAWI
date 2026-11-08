import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:5000", changeOrigin: false },
      "/legacy": { target: "http://127.0.0.1:5000", changeOrigin: false },
      "/static": { target: "http://127.0.0.1:5000", changeOrigin: false },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
