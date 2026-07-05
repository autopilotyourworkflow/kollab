# Kollab — frontend

React 19 + TypeScript + Vite + Tailwind v4. The full product story, setup, and
architecture live in the [root README](../README.md); this note covers only what
is specific to this directory.

```bash
npm install
npm run dev        # http://localhost:5178 (port pinned in vite.config.ts)
npm run build      # typecheck + production bundle -> dist/
```

Requires Node 20.19+ (or 22.12+).

## How data reaches the UI

- `functions/api/shortlist.ts` — Cloudflare Pages Function serving the Python
  pipeline's committed output at `/api/shortlist` (the regeneration command is
  documented at the top of that file).
- `src/data/kols.ts` — the bundled fallback imports that same committed payload,
  so the fallback, the hosted API, and every on-screen number cannot drift.
- `src/lib/api.ts` — fetch + validation + fixtures fallback. Set `VITE_API_URL`
  to point the UI at a live FastAPI backend instead of the Pages Function.

## Handy scripts

- `scripts/shot.mjs` — Playwright screenshot/click-through helper used for
  visual verification (`node scripts/shot.mjs <url> <out.png> ...`).
