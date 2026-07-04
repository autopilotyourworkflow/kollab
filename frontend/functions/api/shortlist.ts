// Cloudflare Pages Function: GET /api/shortlist
//
// Serves the Python pipeline's output so the hosted demo answers over real HTTP
// with the same ShortlistResponse contract as the FastAPI backend. The payload
// is generated at build time by the actual pipeline (backend/app/pipeline.py,
// seed fixtures mode) — regenerate with:
//   cd backend && ./.venv/Scripts/python.exe -c "from app.pipeline import build_shortlist; \
//     from app.sources.seed import SeedDatasetSource; import json; \
//     json.dump(build_shortlist(SeedDatasetSource()).model_dump(by_alias=True), \
//     open('../frontend/functions/api/shortlist.json','w',encoding='utf-8'), ensure_ascii=False)"
// For live per-request compute, run the FastAPI app and point VITE_API_URL at it.
import shortlist from "./shortlist.json"

export const onRequestGet = async () =>
  new Response(JSON.stringify(shortlist), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "cache-control": "public, max-age=300",
    },
  })
