/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: {
          base: '#0f1012',
          surface: '#16171b',
          elevated: '#1c1d22',
          border: '#26272e',
          borderSubtle: '#1e1f25',
          textMuted: '#717382',
          textSecondary: '#a0a2b1',
          textPrimary: '#f0f1f5',
        },
        accent: {
          DEFAULT: '#38bdf8', // Restrained sky blue
          muted: '#0284c7',
          subtle: 'rgba(56, 189, 248, 0.08)',
          border: 'rgba(56, 189, 248, 0.22)',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}
