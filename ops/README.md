# Ops — scheduled re-vet

A shortlist is only true on the day it was built. Comment pods spin up, engagement
collapses, creators go dormant — and the account manager finds out on the client call.
The **scheduled re-vet** re-vets a shortlist on a cadence and pings **only when something
changed that a human should look at**. It turns a one-time deliverable into a monitored
asset — the "operate it, don't just run it" adoption proof.

It ships two ways. The **GitHub Actions workflow is the default and needs nothing to set
up** — it lives in the repo and runs the real backend code. The **n8n workflow** is an
optional alternative for teams that already operate n8n.

## Default: GitHub Actions (self-contained, zero setup)

`.github/workflows/revet.yml` runs `python -m app.revet` (`backend/app/revet.py`):

- **Production trigger:** the `schedule` cron — Mondays 08:00 Asia/Bangkok (01:00 UTC).
- **On-demand trigger:** `workflow_dispatch` — the **Run workflow** button in the Actions tab.

Each run diffs the current shortlist against the previous snapshot and writes a Markdown
report to the run summary, alerting on the three conditions below. The committed run uses
`--demo`: it diffs the deterministic seed against a synthetic healthy baseline, so **every
run visibly demonstrates the alert path AND regression-guards the fraud detectors** — no
credentials, no external services. For real week-over-week drift on a live workspace, set a
`KOLLAB_API_URL` repository variable and run
`python -m app.revet --source api --snapshot <persisted path>` (persist the snapshot with
`actions/cache` or a committed-back file).

## The diff (same policy as the fraud engine)

`diff_snapshots` keeps a per-KOL snapshot (risk level, engagement rate, signal labels) and
emits one alert per change, on three conditions:

| Condition | Fires when |
|---|---|
| Risk worsened | `risk.level` moved clear → medium/high (or medium → high) |
| Engagement drop | `engagementRate` fell more than **40%** vs the snapshot |
| New fraud signal | a `risk.signals` label appears that wasn't there last run |

KOLs new to the shortlist are baselined **silently** (no first-sight noise) — the same
"never assert from absence of data" honesty as vetting. `ENGAGEMENT_DROP_FRAC` is a named,
retunable constant at the top of `app/revet.py`, and the whole diff is unit-tested
(`backend/tests/test_revet.py`).

Alert shape:

> Kollab re-vet: @mimin.glowyskin — risk clear -> high (Comment pod, View spike).
> Review before the next client call.

## Optional: n8n

For teams that already run n8n, `n8n/kol-revet-alert.json` is the same diff as an importable
workflow with a Slack alert node — operable in the n8n UI, no engineer required.

1. n8n (v1.x) → **Workflows → Import from File** → `ops/n8n/kol-revet-alert.json`.
2. Set `KOLLAB_API_URL` (base URL of the Kollab API, no trailing slash) on the n8n process,
   or edit it directly in the **Fetch shortlist** node on n8n Cloud.
3. Open **Slack alert**, attach a bot-token credential (`chat:write`, bot invited to the
   channel) — or swap the node for email / LINE Notify; nothing upstream depends on it.
4. **Activate** the workflow. The Schedule node is the weekly production trigger; the webhook
   (`GET <n8n-host>/webhook/kollab-revet`) fires the identical flow on demand.

The n8n Code node keeps its snapshot in workflow static data and emits the same audit record
(`loggedAt`, `workflow`, `handle`, `change`, `summary`) into n8n's execution history.
