// Wrapper to launch Vite dev server from the web/ directory
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'
const __dirname = dirname(fileURLToPath(import.meta.url))
process.chdir(__dirname)
await import('./node_modules/vite/bin/vite.js')
