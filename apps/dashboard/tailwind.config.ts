import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          DEFAULT: "#0a0d12",
          raised: "#11151c",
          card: "#141922",
          hover: "#1a2029",
          border: "#232a36",
        },
        text: {
          DEFAULT: "#e7e9ee",
          muted: "#8b93a3",
          faint: "#5b6472",
        },
        accent: {
          DEFAULT: "#8b5cf6",
          hover: "#7c3aed",
          soft: "rgba(139, 92, 246, 0.14)",
        },
        status: {
          green: "#22c55e",
          "green-soft": "rgba(34, 197, 94, 0.14)",
          amber: "#f59e0b",
          "amber-soft": "rgba(245, 158, 11, 0.14)",
          red: "#ef4444",
          "red-soft": "rgba(239, 68, 68, 0.14)",
          gray: "#6b7280",
          "gray-soft": "rgba(107, 114, 128, 0.14)",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 rgba(255,255,255,0.03) inset, 0 8px 24px rgba(0,0,0,0.24)",
      },
    },
  },
  plugins: [],
};

export default config;
