import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// GitHub Pages serves a project site from /<repo>/, so assets must be requested from that
// subpath. Override with VITE_BASE if you deploy elsewhere (e.g. a custom domain → "/").
const base = process.env.VITE_BASE ?? '/PC-Pricing-Dashboard/'

// https://vite.dev/config/
export default defineConfig({
  base,
  plugins: [react()],
})
