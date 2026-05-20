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
        // Paleta Orgatec extraída do logo (navy → blue → cyan)
        brand: {
          navy:   "#1E3A8A",
          blue:   "#2563EB",
          sky:    "#0EA5E9",
          cyan:   "#22D3EE",
          dark:   "#0B1E3F",   // navy mais escuro do gradient
          ink:    "#0F172A",   // texto principal
        },
        // Cores semânticas mantidas para compatibilidade
        success: "#16A34A",
        warning: "#D97706",
        danger:  "#DC2626",
      },
      backgroundImage: {
        "brand-gradient":      "linear-gradient(135deg, #1E3A8A 0%, #2563EB 50%, #22D3EE 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, #DBEAFE 0%, #BFDBFE 50%, #CFFAFE 100%)",
        "brand-vertical":      "linear-gradient(180deg, #0B1E3F 0%, #1E3A8A 50%, #2563EB 100%)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
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
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up":   "accordion-up 0.2s ease-out",
        "fade-in":        "fade-in 0.3s ease-out",
        "slide-up":       "slide-up 0.3s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}
