/**
 * kollab-keepwarm — a Cloudflare Worker that pings the Render backend's /health on a
 * schedule so the free-tier instance doesn't sleep. A sleeping instance cold-starts in
 * ~30–50s, which is what made the first load of /app slow; keeping it warm removes that.
 *
 * Deploy:  cd ops/keepwarm && npx wrangler deploy   (Cloudflare account: autopilotyourworkflow)
 * Pause:   comment out the crons in wrangler.toml and redeploy, or delete the Worker.
 *
 * Cost: Cloudflare Workers free tier includes cron triggers. Pinging every 10 min keeps
 * the Render service awake 24/7 — within Render's free 750 instance-hours/month for a
 * single service. Drop the frequency (or remove this) if you'd rather let it sleep.
 */
const TARGET = "https://kollab-api.onrender.com/health"

export default {
  async scheduled(_event, _env, ctx) {
    ctx.waitUntil(fetch(TARGET, { method: "GET" }).catch(() => {}))
  },
  async fetch() {
    // Hitting the Worker URL directly also warms the backend (and confirms it's deployed).
    try {
      await fetch(TARGET, { method: "GET" })
    } catch {
      /* best-effort */
    }
    return new Response("kollab-keepwarm: pings kollab-api /health every 10 min\n", {
      status: 200,
      headers: { "content-type": "text/plain" },
    })
  },
}
