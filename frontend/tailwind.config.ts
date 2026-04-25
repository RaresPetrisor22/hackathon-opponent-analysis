import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#070b18",
        surface: "#0f1830",
        "surface-2": "#1a2747",
        "surface-3": "#243358",
        accent: "#60a5fa",
        "accent-dim": "#3b82f6",
        "accent-bright": "#93c5fd",
        "accent-deep": "#1d4ed8",
        muted: "#475569",
        "muted-fg": "#94a3b8",
        danger: "#f87171",
        warning: "#fbbf24",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
      },
      boxShadow: {
        glow: "0 0 24px -6px rgba(96, 165, 250, 0.35)",
        "glow-sm": "0 0 12px -4px rgba(96, 165, 250, 0.4)",
        card: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 8px 24px -12px rgba(0,0,0,0.6)",
      },
      backgroundImage: {
        "card-gradient":
          "linear-gradient(180deg, rgba(96,165,250,0.04) 0%, rgba(15,24,48,0) 60%)",
      },
    },
  },
  plugins: [],
};

export default config;
