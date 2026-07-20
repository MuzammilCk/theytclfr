import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// ytclfr Nexus — 3D console for the ytclfr video-intelligence pipeline.
// Dev proxy forwards /api/* to a locally-running FastAPI backend (live mode).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        // Split the heavy 3D stack + React + vendor libs so the initial parse
        // is lean and the 3D bundle caches independently. Kept as a DAG
        // (index -> {three, react, vendor}; three/vendor -> react) so Rollup
        // emits no circular-chunk warning.
        manualChunks: {
          react: ["react", "react-dom"],
          three: ["three", "@react-three/fiber", "@react-three/drei", "@react-three/postprocessing"],
          vendor: ["gsap", "@gsap/react", "zustand"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
