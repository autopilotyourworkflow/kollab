# Go-live runbook

Everything in this repo *also* runs credential-free — build the frontend without
`VITE_API_URL` and it serves the committed pipeline output with no keys. This runbook
is the procedure that already took the same code live (Render + Neon): real sourcing,
real LLM extraction, real per-request compute. Total hands-on time ≈ 20 minutes. Keys go in environment
variables only — never in the repo, never in a chat.

## 1. Apify token (live TikTok sourcing)

1. Sign in at https://console.apify.com (free tier includes starter credit;
   pay-per-event actors bill per result — see the run-depth table below).
2. **Settings → API & Integrations → Personal API tokens → Create new token.**
3. Put it in `backend/.env` (gitignored) as `APIFY_TOKEN=apify_api_…`.

No actor setup is needed — the adapter calls `clockworks/tiktok-scraper` and
`clockworks/tiktok-comments-scraper` on demand. Costs are governed twice: the
run-depth plan the user picks (estimate + hard cap; the loop stops *before*
crossing the cap) and the server ceiling `KOLLAB_RUN_BUDGET_USD`.

| depth | volumes | est. | default cap |
|---|---|---|---|
| Scan | 8 creators × 50 comments | ≈$0.28 | $0.50 |
| Standard | 20 × 120 | ≈$1.33 | $1.75 |
| Deep | 40 × 150 | ≈$3.20 | $4.00 |

## 2. Anthropic key (Brand DNA + citation-validated rerank)

1. https://console.anthropic.com → **API keys → Create key** (a few dollars of
   credit is more than enough; both touchpoints use one mid-tier model).
2. `backend/.env`: `ANTHROPIC_API_KEY=sk-ant-…`
3. Optional fallback: a Google AI Studio key as `GEMINI_API_KEY` — used only
   when Claude fails; without either key the chain lands on the labeled
   rules skeleton, never a fake brief.

Local smoke test after keys:

```bash
cd backend
# install the live extras once:
#   .venv/Scripts/pip install -e .[live]      (Windows)
#   .venv/bin/pip install -e ".[live]"        (macOS/Linux)
python -m uvicorn app.main:app --reload
# then: GET /health         -> apify_enabled / llm_enabled true
#       POST /api/brand-dna -> {"website": "<a real brand site>"}  (source: "claude")
#       POST /api/shortlist?preset=scan  with a brief, KOLLAB_SOURCE=apify
#       ^ the FIRST live actor run is a calibration run — inspect the pull
#         before trusting numbers.
#       POST /api/shortlist?preset=scan&expand=1  -> a second run that skips
#         every creator the brand already holds (dedup reported in
#         excludedKnown). History lives in kollab.db (KOLLAB_DB to relocate;
#         ephemeral on Render free tier — losing it only means re-buying data).
```

## 3. Render deploy (live backend)

1. https://dashboard.render.com → **New → Blueprint** → connect this repo.
   Render reads the repo-root `render.yaml` (free-tier web service, health
   check on `/health`).
2. In the service's **Environment** tab, set the secrets the blueprint marked
   `sync: false`: `APIFY_TOKEN`, `ANTHROPIC_API_KEY` (+ `GEMINI_API_KEY`).
   Leave `KOLLAB_SOURCE=seed` until the calibration run looks right.
3. Deploy; verify `https://<service>.onrender.com/health`.
   Free-tier note: the instance sleeps when idle — first request after a pause
   takes ~30s. Fine for a demo; a paid instance removes it.

## 4. Point the hosted UI at the live backend

```bash
cd frontend
VITE_API_URL=https://<service>.onrender.com npm run build
npx wrangler pages deploy dist --project-name kollab --branch main
```

With `VITE_API_URL` set, the UI fetches shortlists from the live API and
`/app/new` runs real Brand-DNA extraction (green "extracted live via claude"
badge). Without it, the static demo keeps serving the committed pipeline
output — nothing breaks in either direction.

## 5. Rollback

The static demo is independent of the live backend: redeploy the frontend
without `VITE_API_URL` (or just delete the Render service) and the site falls
back to the committed pipeline payload instantly.
