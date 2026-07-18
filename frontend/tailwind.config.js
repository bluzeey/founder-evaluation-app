/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#FAF9F6",
        ink: "#0A192F",
        action: "#2563EB",
        verified: "#16A34A",
        uncertain: "#D97706",
        contradiction: "#DC2626",
        missing: "#6B7280",
        inferred: "#9333EA",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["SF Mono", "monospace"],
      },
    },
  },
  plugins: [],
}
