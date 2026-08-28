import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/social_media_agent/web_assets",
    emptyOutDir: true,
    manifest: "asset-manifest.json",
    rollupOptions: { input: "index.html" },
  },
});
