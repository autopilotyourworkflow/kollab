"""Closed-loop delivery re-rank — a small, bounded, honest nudge from logged outcomes.

The ONLY source of campaign-outcome truth is what the user logs (Apify/public data carries
none), so this is strictly a learning loop:
  - n == 0  → a NEUTRAL (0) adjustment + an explicit learning-state label. Nothing is
    fabricated and the shortlist is byte-identical to the no-ledger case.
  - n >= 1  → the average delivered/projection ratio nudges fit, HARD-CLAMPED to ±6 so a
    couple of data points can never dominate the measured factors, and always labelled
    "estimated, from your N logged deliveries" with N visible.

Pure + deterministic; the "ML" is deliberately a transparent clamped average, not a hidden
model. A real learned model is roadmap, and labelled as such in the UI.
"""

from __future__ import annotations

DELIVERY_NUDGE_K = 12       # ratio→points scale (a 2× over-delivery ≈ +12 before clamping)
DELIVERY_NUDGE_CLAMP = 6    # hard cap: outcomes can only ever nudge, never dominate the fit


def delivery_adjustment(ratios: list[float]) -> tuple[int, str]:
    """Return (fit_adjustment, label). Neutral + learning label when no outcomes are logged."""
    if not ratios:
        return 0, ("No delivery outcomes logged yet — fit unchanged. Log a delivery to start "
                   "the feedback loop.")
    mean = sum(ratios) / len(ratios)
    raw = (mean - 1.0) * DELIVERY_NUDGE_K
    adj = int(max(-DELIVERY_NUDGE_CLAMP, min(DELIVERY_NUDGE_CLAMP, round(raw))))
    n = len(ratios)
    unit = "delivery" if n == 1 else "deliveries"
    return adj, (f"Estimated from your {n} logged {unit}: delivered {mean:.2f}× projection on "
                 f"average → fit {adj:+d}.")
