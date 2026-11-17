import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#130807", 700: "#3a2a27", 500: "#6b5a55", 300: "#a8988f" },
        rust: { DEFAULT: "#A94513", dark: "#8a370e", light: "#f3dccd" },
        amber: { DEFAULT: "#D17A2E", light: "#f7e2c8" },
        ivory: { DEFAULT: "#FFF3E6", deep: "#f8e6d1", card: "#fffaf4" },
      },
      fontFamily: {
        serif: ["var(--font-fraunces)", "Libre Baskerville", "Georgia", "serif"],
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(19,8,7,0.04), 0 4px 16px rgba(19,8,7,0.05)",
      },
    },
  },
  plugins: [],
};

export default config;
