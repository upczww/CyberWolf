/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        wolf: '#dc2626',
        good: '#16a34a',
        seer: '#7c3aed',
        witch: '#0891b2',
        hunter: '#ea580c',
        idiot: '#ca8a04',
      },
    },
  },
  plugins: [],
}
