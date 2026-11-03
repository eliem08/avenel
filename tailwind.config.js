/** @type {import('tailwindcss').Config} */
// Part E.2: theme.colors is REPLACED (not extended). Only Part E tokens exist.
// transparent / current are not colors; they let borders and icons inherit (ADR-002).
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      sky: { DEFAULT: '#0593C6', ink: '#047AA5', wash: '#E3F3F9' },
      pink: { DEFAULT: '#D83995', ink: '#B82A7C', wash: '#FBE8F2' },
      paper: '#FCFFFF',
      surface: '#F2F7F9',
      line: '#D7E3E8',
      ink: { DEFAULT: '#0A2533', 2: '#4A6573' },
      ok: '#1F7A4D',
      fail: '#B4232C',
    },
    fontFamily: {
      heading: ["'Readex Pro'", "'IBM Plex Sans Arabic'", 'sans-serif'],
      sans: ["'IBM Plex Sans'", "'IBM Plex Sans Arabic'", 'sans-serif'],
    },
    // Part E.4: shadow only on floating layers.
    boxShadow: { none: 'none', float: '0 8px 24px rgba(10,37,51,0.14)' },
    ringColor: ({ theme }) => ({ DEFAULT: theme('colors.sky.DEFAULT'), ...theme('colors') }),
    ringOffsetColor: ({ theme }) => ({ DEFAULT: theme('colors.paper'), ...theme('colors') }),
    borderColor: ({ theme }) => ({ DEFAULT: theme('colors.line'), ...theme('colors') }),
    extend: {
      borderRadius: { input: '2px', panel: '6px' },
      width: { rail: '220px' },
    },
  },
  corePlugins: { preflight: false },
  plugins: [],
};
