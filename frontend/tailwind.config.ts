import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Colori di gioco ──────────────────────────────────────────────────
        verde: {
          DEFAULT: "#2d5a27",
          dark: "#1e3e1b",
          light: "#3d7a35",
        },
        oro: {
          DEFAULT: "#f5c518",
          light: "#fad54a",
          pale: "#fef3b0",
        },
        crema: "#fffdf5",
        bordo: "#d4c89a",
        // ── Estensioni design system ─────────────────────────────────────────
        loam: "#1a2e18",        // foreground scuro verde-tinto (foresta profonda)
        stone: "#f0ebe0",       // sfondo sezioni alternate (pietra calda)
        grass: "#6b7860",       // testo secondario (prato secco + verde)
      },
      fontFamily: {
        sans:    ["Nunito", "system-ui", "-apple-system", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      boxShadow: {
        // Verde-tinted soft shadows — mai puro nero
        soft:      "0 4px 20px -2px rgba(45, 90, 39, 0.12)",
        float:     "0 12px 40px -8px rgba(45, 90, 39, 0.18)",
        "float-lg":"0 20px 60px -12px rgba(45, 90, 39, 0.22)",
        oro:       "0 4px 20px -2px rgba(245, 197, 24, 0.22)",
        "oro-lg":  "0 12px 40px -8px rgba(245, 197, 24, 0.30)",
      },
      borderRadius: {
        "4xl": "2rem",
        "5xl": "3rem",
        "6xl": "4rem",
      },
      backgroundImage: {
        // Gradient sottile per le card carriera
        "card-header": "linear-gradient(135deg, #f5c518 0%, #fad54a 100%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
