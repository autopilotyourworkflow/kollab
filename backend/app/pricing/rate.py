"""Fraud-adjusted fair-rate ESTIMATOR — an editable CPM applied to measured organic reach.

⚠️  HONESTY (locked scope: no invented rate cards / tier benchmarks). This is deliberately
    NOT a market rate. It is exactly three things multiplied:

        median ORGANIC views  ×  a CPM the OPERATOR sets  ×  authenticity discount

    - median organic views: the creator's OWN outlier-excluded median (median_views already
      drops boosted/spike posts) — so you never price non-repeating boosted reach as organic;
    - CPM: the ONE assumption the user provides (THB per 1,000 views), editable per-creator in
      the UI, default a neutral placeholder with NO tier/vertical variation. Double it and the
      band doubles — the estimate is linear in the user's number, by construction;
    - authenticity: 0-100 from the fraud layer, so a pod/bought-follower creator's inflated
      reach is discounted, not paid for.

    Every value is provenance 'estimated', the arithmetic is shown (`method`), and the band is
    WITHHELD (None) when the video sample is too thin to price. A reviewer can read every input.
"""

from __future__ import annotations

from app.config import DEFAULT_CPM_THB
from app.fraud.cohort import median_views
from app.raw import RawKOL
from app.schemas import RateBand, RateBasis

# We can price a creator's reach from as little as ONE sampled video — it's the SAME
# outlier-excluded median already shown in the creator's "median views" metric, so pricing
# off it is consistent with what the table displays. A live search feed usually surfaces only
# a few of a creator's videos, so a higher floor would withhold the estimate on most live
# creators (even on Deep). Below RATE_THIN_SAMPLE the sample is thin: still priced, but the
# basis flags it so the UI labels the estimate "indicative" and points at a deeper run.
RATE_MIN_VIDEOS = 1      # need at least one video for a median; 0 videos -> can't price
RATE_THIN_SAMPLE = 5     # at/below this the sample is thin -> priced but flagged indicative
RATE_BAND_SPREAD = 0.20  # ±20% band around the point estimate (honest uncertainty, not precision)


def fair_rate_band(median_organic_views: int, authenticity: int, cpm_thb: float) -> RateBand:
    """The band, pure and linear in the CPM. Authenticity clamps reach to [0,1]×."""
    disc = max(0.0, min(1.0, authenticity / 100.0))
    point = (median_organic_views * disc) / 1000.0 * cpm_thb
    return RateBand(low=int(round(point * (1 - RATE_BAND_SPREAD))),
                    high=int(round(point * (1 + RATE_BAND_SPREAD))))


def rate_basis_for(kol: RawKOL, authenticity: int, cpm_thb: float | None = None) -> RateBasis | None:
    """Full transparent basis for one creator, or None (withheld) when videos are too few."""
    if len(kol.videos) < RATE_MIN_VIDEOS:
        return None
    cpm = DEFAULT_CPM_THB if cpm_thb is None else float(cpm_thb)
    n = len(kol.videos)
    mov = int(median_views(kol))  # outlier-excluded organic median
    band = fair_rate_band(mov, authenticity, cpm)
    thin = n < RATE_THIN_SAMPLE
    method = (
        f"{mov:,} organic views/post (median of {n} sampled video{'s' if n != 1 else ''}, "
        f"boosted excluded) × ฿{cpm:g} CPM (your assumption) × {authenticity}% authenticity "
        f"⇒ ฿{band.low:,}–฿{band.high:,} per post."
        + (" Thin sample — indicative; a deeper run firms it up." if thin else "")
        + " Edit the CPM to your own rate — this is not a market rate card."
    )
    return RateBasis(median_organic_views=mov, cpm_thb=cpm, authenticity=int(authenticity),
                     videos_sampled=n, band=band, method=method)
