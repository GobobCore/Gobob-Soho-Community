/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Gobob brand — 暖橙主色 + 配套语义色
        primary: {
          50:  '#FDF6EE',
          100: '#FAE6CD',
          200: '#F4CC9A',
          300: '#EDB776',
          400: '#E59E56',
          500: '#E08A44',
          600: '#C97636',
          700: '#A85F26',
          800: '#7F4A1E',
          900: '#5C3616',
        },
      },
      fontFamily: {
        sans: [
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'sans-serif',
        ],
      },
      boxShadow: {
        'soft': '0 2px 12px rgba(15, 23, 42, 0.06)',
        'lift': '0 8px 24px rgba(15, 23, 42, 0.08)',
        'glow-primary': '0 4px 20px rgba(224, 138, 68, 0.32)',
      },
      animation: {
        'fade-in-up': 'fadeInUp 0.4s ease-out',
        'pulse-soft': 'pulseSoft 2.4s ease-in-out infinite',
      },
      keyframes: {
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.78' },
        },
      },
    },
  },
  plugins: [],
};
