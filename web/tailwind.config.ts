import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: {
          light: '#FDFDF7',
          dark: '#09090B',
        },
        sidebar: {
          light: '#F8F8F2',
          dark: '#111113',
        },
        primary: {
          DEFAULT: '#D4A27F',
          dark: '#0E0E0E',
        },
        border: {
          light: '#E5E5E5',
          dark: '#27272A',
        },
        muted: {
          light: '#71717A',
          dark: '#A1A1AA',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
