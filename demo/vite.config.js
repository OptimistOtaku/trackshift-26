import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// publicDir points OUTSIDE this project at the frozen data contract.
//
//   artifacts/demo/index.json   ->  served at  /index.json
//   artifacts/demo/model.json   ->  served at  /model.json
//   artifacts/demo/races/R08.json -> served at /races/R08.json
//   artifacts/demo/replay/R08.json -> served at /replay/R08.json
//
// Two things this buys us:
//   1. `npm run dev` serves the real artifacts with no copy step, so a re-export by
//      Aditya is picked up on reload. Nothing in this app hardcodes a headline number.
//   2. `npm run build` copies them into dist/, so dist/ is a self-contained offline
//      bundle. That is what passes the wifi-off drill in docs/JUDGE_QA.md section 4.
//
// If publicDir ever misbehaves, src/lib/data.js falls back to relative paths up to the
// repo root, so serving the repo with `python -m http.server` also works. Do not
// "simplify" that fallback away — it is the parachute for the parachute.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  publicDir: '../artifacts/demo',
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // One bundle. Nothing is fetched from a CDN and nothing is code-split, so there is
    // no second request that can fail on stage.
    assetsInlineLimit: 0,
  },
  server: {
    port: 5173,
    strictPort: false,
  },
});
