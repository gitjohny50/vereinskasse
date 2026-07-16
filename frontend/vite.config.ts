import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Im Entwicklungsbetrieb läuft das Frontend auf :5173 und leitet /api an das
// Backend (:8000) weiter. Dadurch nutzt der Code überall relative /api-Pfade,
// die im Produktivbetrieb (Backend liefert das gebaute Frontend aus) ebenfalls
// funktionieren.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
