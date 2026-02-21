/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
        // 트레이딩 전용 팔레트
        t: {
          bg: { DEFAULT: '#0a0a0f', card: '#12121a', elevated: '#1a1a28' },
          border: { DEFAULT: '#1e1e2e', hover: '#2a2a3d', active: '#3a3a50' },
          text: { primary: '#e2e8f0', secondary: '#94a3b8', muted: '#64748b' },
          accent: { DEFAULT: '#f59e0b', hover: '#d97706', glow: '#f59e0b33' },
          bull: '#ef4444',
          bear: '#3b82f6',
          success: '#10b981',
          warning: '#f59e0b',
          danger: '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Pretendard', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['Fira Code', 'Consolas', 'Monaco', 'monospace'],
      },
      boxShadow: {
        'glow-accent': '0 0 12px 2px rgba(245, 158, 11, 0.15)',
        'glow-bull': '0 0 10px 2px rgba(239, 68, 68, 0.12)',
        'glow-bear': '0 0 10px 2px rgba(59, 130, 246, 0.12)',
        'glow-sm': '0 0 6px 1px rgba(245, 158, 11, 0.10)',
        'glow-success': '0 0 10px 2px rgba(16, 185, 129, 0.12)',
      },
      animation: {
        'pulse-live': 'pulse-live 2s ease-in-out infinite',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'flash-green': 'flash-green 0.6s ease-out',
        'flash-red': 'flash-red 0.6s ease-out',
      },
      keyframes: {
        'pulse-live': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'flash-green': {
          '0%': { backgroundColor: 'rgba(16, 185, 129, 0.2)' },
          '100%': { backgroundColor: 'transparent' },
        },
        'flash-red': {
          '0%': { backgroundColor: 'rgba(239, 68, 68, 0.2)' },
          '100%': { backgroundColor: 'transparent' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-card': 'linear-gradient(135deg, rgba(26, 26, 40, 0.5) 0%, rgba(18, 18, 26, 0.8) 100%)',
      },
    },
  },
  plugins: [],
}
