# Ops — scheduled re-vet (n8n)

A shortlist is only true on the day it was built. Comment pods spin up, engagement
collapses, creators go dormant — and the account manager finds out on the client call.
The workflow in `n8n/kol-revet-alert.json` re-pulls the shortlist every week, diffs it
against the previous run, and pings the team **only when something changed that a human
should look at**. It turns a one-time deliverable into a monitored asset, and it's
operable by the agency team in the n8n UI — no engineer required.

## What one run does

```
weekly cron ─┐
             ├─▶ GET $KOLLAB_API_URL/api/shortlist ─▶ diff vs snapshot ─▶ any alerts?
demo webhook ┘                                        (static data)        │        │
                                                                     yes ─┤        └─ no ─▶ NoOp
                                                          Slack + audit log entry
```

The Code node keeps a per-KOL snapshot in n8n **workflow static data** and emits one
item per alert, on three conditions:

| Condition | Fires when |
|---|---|
| Risk worsened | `risk.level` moved clear → medium/high (or medium → high) |
| Engagement drop | `engagementRate` fell more than **40%** vs the snapshot |
| New fraud signal | a `risk.signals` label appears that wasn't there last run |

Then it updates the snapshot, so the next run diffs against this one. KOLs new to the
shortlist are baselined silently (no first-sight noise). The 40% threshold is a named
constant at the top of the Code node — retunable in the UI, same policy as
`backend/app/fraud/signals.py`.

Alert message shape:

> Kollab re-vet: @glowwithnan — risk clear → high (Comment pod: 41 accounts across
> 6 unrelated creators in 14 days). Review before the next client call.

## Import

1. n8n (v1.x) → **Workflows → Import from File** → `ops/n8n/kol-revet-alert.json`.
2. Set the `KOLLAB_API_URL` environment variable (below).
3. Open **Slack alert** and attach a real credential (below).
4. **Activate** the workflow — the cron and the production webhook URL only run while active.

## `KOLLAB_API_URL`

Base URL of the Kollab API, **no trailing slash** — e.g. `http://127.0.0.1:8000`
locally, or the deployed backend. The HTTP node calls
`{{ $env.KOLLAB_API_URL }}/api/shortlist`.

Set it on the n8n process (self-hosted: `docker run -e KOLLAB_API_URL=…` or an entry
in the systemd/env file). n8n Cloud doesn't expose custom env vars — there, edit the
URL directly in the **Fetch shortlist** node instead.

## Two triggers, one flow

- **Production trigger:** the Schedule node — every Monday 08:00, Asia/Bangkok
  (timezone is set in the workflow settings, not the server clock).
- **Demo trigger:** the webhook — `GET https://<n8n-host>/webhook/kollab-revet` fires
  the *identical* flow immediately, which is what makes an on-camera demo deterministic
  instead of "wait until Monday."

Use the webhook's **Production URL** (workflow active), not the editor's Test URL:
the snapshot lives in workflow static data, which n8n only persists across production
executions. Editor test runs always start from an empty snapshot.

Honest note for demos: the fixtures API is deterministic, so firing the webhook twice
against an unchanged backend correctly reports "no changes." To show the alert branch,
fire once to baseline, change what the API returns (edit a fixture, or point
`KOLLAB_API_URL` at a stage copy where a KOL's story worsened), then fire again.

## Slack placeholder

The Slack node ships pointing at `#kol-vetting` with a placeholder credential — the
import will show a credential warning until it's filled in. The agency needs:

- a Slack app with a **bot token** (`chat:write` scope),
- the bot invited to the target channel,
- that token saved as an n8n **Slack API** credential and selected on the node.

Nothing upstream depends on Slack — swapping it for email or LINE Notify means
replacing one node, not touching the diff logic.

## Audit trail

Every alert also flows through the **Audit log entry** Set node, which emits a
structured record (`loggedAt`, `workflow`, `handle`, `change`, `summary`) preserved in
n8n's execution history — a reviewable trail of what was flagged and when. Appending
it to a Google Sheet or database for a longer-lived log is a one-node extension,
deliberately left as roadmap.
