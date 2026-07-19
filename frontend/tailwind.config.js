/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#FDFBF7",
        manila: "#E6D9C3",
        "manila-dark": "#D4C5AD",
        ink: "#1F1F1F",
        action: "#B58A3E",
        "action-dark": "#8F6B2B",
        verified: "#5B7C3A",
        uncertain: "#B58A3E",
        contradiction: "#B52B24",
        missing: "#8A8279",
        inferred: "#6B5B95",
        brass: "#B58A3E",
        concrete: "#8A8279",
        paper: "#FDFBF7",
        highlight: "#F4D06F",
      },
      fontFamily: {
        display: ["Sora", "system-ui", "sans-serif"],
        sans: ["Work Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      boxShadow: {
        paper: "0 1px 2px rgba(31,31,31,0.06), 0 3px 8px rgba(31,31,31,0.08)",
        "paper-lg": "0 4px 6px rgba(31,31,31,0.05), 0 12px 24px rgba(31,31,31,0.10)",
        stamp: "0 8px 20px rgba(181,43,36,0.18)",
      },
      rotate: {
        1: "1deg",
        "-1": "-1deg",
        2: "2deg",
        "-2": "-2deg",
      },
      animation: {
        stamp: "stamp 0.25s ease-out forwards",
      },
      keyframes: {
        stamp: {
          "0%": { opacity: "0", transform: "scale(1.15) rotate(-8deg)" },
          "100%": { opacity: "0.85", transform: "scale(1) rotate(-3deg)" },
        },
      },
    },
  },
  plugins: [],
}
