/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Paleta Direção Leve (deck-comercial)
        brand: {
          bg:       "#EAF4FA",
          cloud:    "#F4F9FC",
          surface:  "#FFFFFF",
          pale:     "#B8DDEE",
          ink:      "#0E2A47",
          "ink-soft": "#3F5A78",
          navy:     "#1A3A6B",
          blue:     "#5BA9D6",
          azure:    "#7BC8E0",
          // alias de compatibilidade
          cyan:     "#7BC8E0",
          dark:     "#0E2A47",
          sky:      "#7BC8E0",
        },
        success: "#16A34A",
        warning: "#D97706",
        danger:  "#DC2626",
        // Financial Dashboard tokens — UI/UX Pro Max
        profit:  "#16A34A",
        loss:    "#DC2626",
        "neutral-fin": "#94A3B8",
      },
      backgroundImage: {
        "brand-gradient":      "linear-gradient(135deg, #1A3A6B 0%, #5BA9D6 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, #EAF4FA 0%, #B8DDEE 100%)",
        "brand-vertical":      "linear-gradient(180deg, #0E2A47 0%, #1A3A6B 100%)",
        "featured-card":       "linear-gradient(160deg, #1A3A6B 0%, #0d4f7a 100%)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans:    ["Manrope", "system-ui", "-apple-system", "sans-serif"],
        jakarta: ["Plus Jakarta Sans", "Manrope", "system-ui", "sans-serif"],
        serif:   ["Instrument Serif", "Georgia", "serif"],
        mono:    ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        xs: "0 1px 2px rgba(15,23,42,.05)",
        card: "0 1px 2px rgba(15,23,42,.05), 0 1px 3px rgba(15,23,42,.06)",
        "card-hover": "0 4px 6px rgba(15,23,42,.05), 0 10px 15px rgba(15,23,42,.08)",
        glow: "0 0 0 3px rgba(37, 99, 235, 0.15)",
      },
      keyframes: {
        "accordion-down": { from: { height: "0" }, to: { height: "var(--radix-accordion-content-height)" } },
        "accordion-up":   { from: { height: "var(--radix-accordion-content-height)" }, to: { height: "0" } },
        "fade-in":        { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up":       { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "wave-flow":      { from: { transform: "translateX(0)" }, to: { transform: "translateX(-120px)" } },
        "compass-spin":   { from: { transform: "rotate(0deg)" }, to: { transform: "rotate(360deg)" } },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up":   "accordion-up 0.2s ease-out",
        "fade-in":        "fade-in 0.3s ease-out",
        "slide-up":       "slide-up 0.3s ease-out",
        "wave-flow":      "wave-flow 14s linear infinite",
        "compass-spin":   "compass-spin 90s linear infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
