1: import { defineConfig } from 'vite'
2: import path from 'path'
3: import tailwindcss from '@tailwindcss/vite'
4: import react from '@vitejs/plugin-react'
5: 
6: export default defineConfig({
7:   plugins: [
8:     // The React and Tailwind plugins are both required for Make, even if
9:     // Tailwind is not being actively used – do not remove them
10:     react(),
11:     tailwindcss(),
12:   ],
13:   resolve: {
14:     alias: {
15:       // Alias @ to the src directory
16:       '@': path.resolve(__dirname, './src'),
17:     },
18:   },
19: 
20:   // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
21:   assetsInclude: ['**/*.svg', '**/*.csv'],
22: })
23: 