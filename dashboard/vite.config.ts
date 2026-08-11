import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Use relative path so it can be hosted in any subdirectory on XAMPP
const base = './'

// https://vite.dev/config/
export default defineConfig({
  base,
  plugins: [react()],
})
