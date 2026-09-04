import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        abyss: {
          950: "#050b14",
          900: "#0a1420",
          800: "#0f1e2e",
          700: "#16293b",
          600: "#1f3a52",
        },
        teal: {
          glass: "#0d2430",
          deep: "#0a1f28",
        },
        trench: {
          950: "#03080f",
          900: "#06111a",
          800: "#0a1925",
          700: "#112434",
        },
        cyan: {
          accent: "#22d3ee",
          dim: "#0891b2",
        },
        foam: {
          500: "#8ddff2",
          300: "#d7f7ff",
        },
        alert: {
          critical: "#f87171",
          high: "#fb923c",
          medium: "#facc15",
          low: "#94a3b8",
          unknown: "#c084fc",
        },
      },
      boxShadow: {
        "glow-cyan": "0 0 0 1px rgba(34,211,238,0.35), 0 0 16px rgba(34,211,238,0.35)",
        "glow-critical": "0 0 0 1px rgba(248,113,113,0.4), 0 0 16px rgba(248,113,113,0.35)",
        "glow-unknown": "0 0 0 1px rgba(192,132,252,0.35), 0 0 14px rgba(192,132,252,0.3)",
        panel: "0 28px 60px rgba(2, 8, 15, 0.38)",
      },
      fontFamily: {
        sans: ["Segoe UI Variable", "Aptos", "Segoe UI", "system-ui", "sans-serif"],
        display: ["Bahnschrift", "Segoe UI Variable", "Aptos", "sans-serif"],
        mono: ["Consolas", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
