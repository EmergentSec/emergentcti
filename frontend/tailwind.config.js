/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        surface: 'var(--surface)',
        surface2: 'var(--surface-2)',
        surface3: 'var(--surface-3)',
        hover: 'var(--hover)',
        card: { DEFAULT: 'var(--card)', foreground: 'var(--foreground)' },
        popover: { DEFAULT: 'var(--popover)', foreground: 'var(--foreground)' },
        primary: { DEFAULT: 'var(--primary)', foreground: 'var(--on-brand)' },
        brand: { DEFAULT: 'var(--brand)', 2: 'var(--brand-2)', foreground: 'var(--on-brand)' },
        muted: { DEFAULT: 'var(--muted)', foreground: 'var(--muted-foreground)' },
        destructive: { DEFAULT: 'var(--destructive)', foreground: '#ffffff' },
        border: 'var(--border)',
        borderStrong: 'var(--border-strong)',
        input: 'var(--surface-2)',
        ring: 'var(--brand)',
        secondary: { DEFAULT: 'var(--secondary)', foreground: 'var(--secondary-foreground)' },
        accent: { DEFAULT: 'var(--accent)', foreground: 'var(--accent-foreground)' },
        cat: {
          green: 'var(--cat-green)', blue: 'var(--cat-blue)', purple: 'var(--cat-purple)',
          orange: 'var(--cat-orange)', pink: 'var(--cat-pink)', yellow: 'var(--cat-yellow)',
        },
        conf: {
          critical: 'var(--conf-critical)', high: 'var(--conf-high)',
          medium: 'var(--conf-medium)', low: 'var(--conf-low)',
        },
      },
      fontFamily: {
        sans: ['Hanken Grotesk', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 4px)',
        sm: 'calc(var(--radius) - 7px)',
      },
    },
  },
  plugins: [],
}
