const withAlpha = (value) =>
  `color-mix(in srgb, ${value} calc(<alpha-value> * 100%), transparent)`

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        background: withAlpha('var(--background)'),
        foreground: withAlpha('var(--foreground)'),
        surface: withAlpha('var(--surface)'),
        surface2: withAlpha('var(--surface-2)'),
        surface3: withAlpha('var(--surface-3)'),
        hover: withAlpha('var(--hover)'),
        card: { DEFAULT: withAlpha('var(--card)'), foreground: withAlpha('var(--foreground)') },
        popover: { DEFAULT: withAlpha('var(--popover)'), foreground: withAlpha('var(--foreground)') },
        primary: { DEFAULT: withAlpha('var(--primary)'), hover: withAlpha('var(--primary-hover)'), soft: withAlpha('var(--primary-soft)'), foreground: withAlpha('var(--on-primary)') },
        brand: { DEFAULT: withAlpha('var(--brand)'), 2: withAlpha('var(--brand-2)'), foreground: withAlpha('var(--on-brand)') },
        muted: { DEFAULT: withAlpha('var(--muted)'), foreground: withAlpha('var(--muted-foreground)') },
        destructive: { DEFAULT: withAlpha('var(--destructive)'), foreground: withAlpha('var(--on-destructive)'), soft: withAlpha('var(--destructive-soft)'), ink: withAlpha('var(--destructive-ink)') },
        success: { DEFAULT: withAlpha('var(--success)'), soft: withAlpha('var(--success-soft)'), ink: withAlpha('var(--success-ink)') },
        warning: { DEFAULT: withAlpha('var(--warning)'), soft: withAlpha('var(--warning-soft)'), ink: withAlpha('var(--warning-ink)') },
        logo: withAlpha('var(--logo)'),
        masthead: {
          DEFAULT: withAlpha('var(--masthead)'), foreground: withAlpha('var(--masthead-foreground)'), muted: withAlpha('var(--masthead-muted)'), border: withAlpha('var(--masthead-border)'),
          action: { DEFAULT: withAlpha('var(--masthead-action)'), hover: withAlpha('var(--masthead-action-hover)'), foreground: withAlpha('var(--masthead-action-foreground)') },
        },
        text3: withAlpha('var(--text-3)'),
        overlay: withAlpha('var(--overlay)'),
        'toggle-thumb': withAlpha('var(--toggle-thumb)'),
        border: withAlpha('var(--border)'),
        borderStrong: withAlpha('var(--border-strong)'),
        input: withAlpha('var(--surface-2)'),
        ring: withAlpha('var(--primary)'),
        secondary: { DEFAULT: withAlpha('var(--secondary)'), foreground: withAlpha('var(--secondary-foreground)') },
        accent: { DEFAULT: withAlpha('var(--accent)'), foreground: withAlpha('var(--accent-foreground)') },
        cat: {
          green: withAlpha('var(--cat-green)'), blue: withAlpha('var(--cat-blue)'), purple: withAlpha('var(--cat-purple)'),
          orange: withAlpha('var(--cat-orange)'), pink: withAlpha('var(--cat-pink)'), yellow: withAlpha('var(--cat-yellow)'),
        },
        'cat-ink': {
          green: withAlpha('var(--cat-green-ink)'), blue: withAlpha('var(--cat-blue-ink)'), purple: withAlpha('var(--cat-purple-ink)'),
          orange: withAlpha('var(--cat-orange-ink)'), pink: withAlpha('var(--cat-pink-ink)'), yellow: withAlpha('var(--cat-yellow-ink)'),
        },
        'cat-soft': {
          green: 'color-mix(in srgb, var(--cat-green) 10%, transparent)',
          blue: 'color-mix(in srgb, var(--cat-blue) 10%, transparent)',
          purple: 'color-mix(in srgb, var(--cat-purple) 10%, transparent)',
          orange: 'color-mix(in srgb, var(--cat-orange) 10%, transparent)',
          pink: 'color-mix(in srgb, var(--cat-pink) 10%, transparent)',
          yellow: 'color-mix(in srgb, var(--cat-yellow) 10%, transparent)',
        },
        conf: {
          critical: withAlpha('var(--conf-critical)'), high: withAlpha('var(--conf-high)'),
          medium: withAlpha('var(--conf-medium)'), low: withAlpha('var(--conf-low)'),
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
