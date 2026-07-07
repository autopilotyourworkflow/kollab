"""Scheduled re-vet sweep — turns a one-time shortlist into a monitored asset.

A shortlist is only true on the day it was built: comment pods spin up, engagement
collapses, creators go dormant — and the account manager finds out on the client call.
This module re-vets a shortlist and diffs it against the previous run's snapshot, raising
an alert ONLY when something changed that a human should look at — the same policy the
fraud engine uses (flag for a human, never auto-act). New creators are baselined silently.

It is deliberately transport-agnostic and self-contained. `python -m app.revet` runs it on
a schedule from GitHub Actions (cron + a manual "Run workflow" dispatch) with ZERO external
services — no n8n instance, no Slack token, nothing to configure. Run it hermetically on the
seed as a deterministic mechanism demo + a detector regression guard (`--demo`), or point it
at a deployed workspace (`--source api`, `KOLLAB_API_URL`) with a persisted `--snapshot` for
real week-over-week drift. The identical diff also ships as an importable n8n workflow
(`ops/n8n/`) for teams that already run n8n.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass

# Alert when engagement falls more than this fraction vs the last snapshot. A named,
# retunable constant — same policy home as the thresholds in app/fraud/signals.py.
ENGAGEMENT_DROP_FRAC = 0.40

_LEVEL_RANK = {"clear": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class Alert:
    handle: str
    kind: str  # "risk_worsened" | "engagement_drop" | "new_signal"
    summary: str


def snapshot_from_kols(kols: list[dict]) -> dict[str, dict]:
    """Reduce a shortlist payload (camelCase, as served at /api/shortlist) to the minimal
    per-KOL state the diff needs: risk level, engagement rate, and the set of signal labels."""
    snap: dict[str, dict] = {}
    for k in kols:
        risk = k.get("risk") or {}
        snap[k["handle"]] = {
            "level": risk.get("level", "clear"),
            "engagementRate": float(k.get("engagementRate", 0.0)),
            "signals": sorted({s.get("label", "") for s in risk.get("signals", []) if s.get("label")}),
        }
    return snap


def diff_snapshots(prev: dict[str, dict], curr: dict[str, dict]) -> list[Alert]:
    """Emit an alert per KOL whose story worsened, on three conditions (risk worsened,
    engagement dropped past the threshold, a new fraud signal appeared). A KOL new to the
    shortlist is baselined SILENTLY — no first-sight noise, the same 'never assert from
    absence of data' honesty as the vetting layer. Only real, human-reviewable changes fire."""
    alerts: list[Alert] = []
    for handle, now in curr.items():
        was = prev.get(handle)
        if was is None:
            continue  # new creator: baseline silently, alert next time only if it worsens

        # 1. Risk level worsened (clear -> medium/high, medium -> high).
        if _LEVEL_RANK.get(now["level"], 0) > _LEVEL_RANK.get(was["level"], 0):
            tail = f" ({', '.join(now['signals'])})" if now["signals"] else ""
            alerts.append(Alert(handle, "risk_worsened", f"risk {was['level']} -> {now['level']}{tail}"))

        # 2. Engagement dropped more than ENGAGEMENT_DROP_FRAC vs the snapshot.
        prev_er = was["engagementRate"]
        if prev_er > 0 and now["engagementRate"] < prev_er * (1 - ENGAGEMENT_DROP_FRAC):
            drop = (prev_er - now["engagementRate"]) / prev_er
            alerts.append(
                Alert(handle, "engagement_drop", f"engagement {prev_er:.1f}% -> {now['engagementRate']:.1f}% (down {drop:.0%})")
            )

        # 3. A fraud signal label appeared that wasn't there last run.
        fresh = [s for s in now["signals"] if s not in was["signals"]]
        if fresh:
            alerts.append(Alert(handle, "new_signal", f"new signal: {', '.join(fresh)}"))
    return alerts


def render_report(alerts: list[Alert], n_kols: int) -> str:
    """Markdown, so it renders straight into a GitHub Actions run summary."""
    lines = ["# Kollab re-vet sweep", ""]
    if not alerts:
        lines.append(f"No changes a human needs to see across {n_kols} shortlisted creators.")
        return "\n".join(lines)
    lines.append(f"**{len(alerts)} alert(s)** across {n_kols} creators - review before the next client call:")
    lines.append("")
    for a in alerts:
        handle = "@" + a.handle.lstrip("@")  # handles already carry a leading @
        lines.append(f"- **{handle}** - {a.summary}")
    return "\n".join(lines)


def load_current(source: str) -> list[dict]:
    """The current shortlist as a list of camelCase KOL dicts, from the seed pipeline
    (hermetic, deterministic) or a deployed API (`KOLLAB_API_URL`)."""
    if source == "api":
        import httpx

        url = os.environ.get("KOLLAB_API_URL", "").rstrip("/")
        if not url:
            raise SystemExit("KOLLAB_API_URL is required for --source api")
        return httpx.get(f"{url}/api/shortlist", timeout=30).json()["kols"]

    # Hermetic seed: deterministic and self-contained. We build the shortlist directly
    # (not via the service) so the sweep never triggers the live LLM rerank or an external
    # DB — the rerank only rewrites why-copy, never the risk/signals/ER the diff reads. This
    # matches CI (no keys, no DATABASE_URL) and keeps a local .env from making live calls.
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("KOLLAB_DB", None)
    from app.pipeline import build_shortlist
    from app.sources.seed import SeedDatasetSource

    return [k.model_dump(by_alias=True) for k in build_shortlist(SeedDatasetSource()).kols]


def _demo_prev(curr: dict[str, dict]) -> dict[str, dict]:
    """A synthetic 'last week was healthy' baseline: every current creator seen as clear
    with strong engagement and no signals. Diffing the seed against it surfaces the seed's
    real flags as alerts — a deterministic demonstration of the alert path in CI, needing
    no persisted state. (Not how production runs; production diffs real successive runs.)"""
    return {
        h: {"level": "clear", "engagementRate": max(s["engagementRate"] * 2, 5.0), "signals": []}
        for h, s in curr.items()
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Kollab scheduled re-vet sweep")
    p.add_argument("--source", choices=["seed", "api"], default="seed")
    p.add_argument("--snapshot", default="", help="JSON snapshot path to diff against + update")
    p.add_argument("--demo", action="store_true", help="diff against a synthetic healthy baseline to show the alert path")
    args = p.parse_args(argv)

    curr = snapshot_from_kols(load_current(args.source))

    if args.demo:
        prev = _demo_prev(curr)
    elif args.snapshot and os.path.exists(args.snapshot):
        with open(args.snapshot, encoding="utf-8") as f:
            prev = json.load(f)
    else:
        prev = {}  # first run: baseline everything silently

    alerts = diff_snapshots(prev, curr)
    report = render_report(alerts, len(curr))
    print(report)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(report + "\n")

    if args.snapshot and not args.demo:
        with open(args.snapshot, "w", encoding="utf-8") as f:
            json.dump(curr, f, indent=2, ensure_ascii=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
