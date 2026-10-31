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
        primary: { DEFAULT: 'var(--primary)', hover: 'var(--primary-hover)', soft: 'var(--primary-soft)', foreground: 'var(--on-primary)' },
        brand: { DEFAULT: 'var(--brand)', 2: 'var(--brand-2)', foreground: 'var(--on-brand)' },
        muted: { DEFAULT: 'var(--muted)', foreground: 'var(--muted-foreground)' },
        destructive: { DEFAULT: 'var(--destructive)', foreground: 'var(--on-destructive)', soft: 'var(--destructive-soft)', ink: 'var(--destructive-ink)' },
        success: { DEFAULT: 'var(--success)', soft: 'var(--success-soft)', ink: 'var(--success-ink)' },
        warning: { DEFAULT: 'var(--warning)', soft: 'var(--warning-soft)', ink: 'var(--warning-ink)' },
        logo: 'var(--logo)',
        masthead: {
          DEFAULT: 'var(--masthead)', foreground: 'var(--masthead-foreground)', muted: 'var(--masthead-muted)', border: 'var(--masthead-border)',
          action: { DEFAULT: 'var(--masthead-action)', hover: 'var(--masthead-action-hover)', foreground: 'var(--masthead-action-foreground)' },
        },
        text3: 'var(--text-3)',
        overlay: 'var(--overlay)',
        'toggle-thumb': 'var(--toggle-thumb)',
        border: 'var(--border)',
        borderStrong: 'var(--border-strong)',
        input: 'var(--surface-2)',
        ring: 'var(--primary)',
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
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: { card: 'var(--shadow-card)' },
      borderRadius: {
        xl: 'var(--radius)',
        lg: 'calc(var(--radius) - 4px)',
        md: 'calc(var(--radius) - 6px)',
        sm: 'calc(var(--radius) - 9px)',
      },
    },
  },
  plugins: [],
}
