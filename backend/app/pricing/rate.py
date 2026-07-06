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

RATE_MIN_VIDEOS = 5      # below this the reach sample is too thin to price — withhold
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
    mov = int(median_views(kol))  # outlier-excluded organic median
    band = fair_rate_band(mov, authenticity, cpm)
    method = (
        f"{mov:,} organic views/post (boosted excluded) × ฿{cpm:g} CPM (your assumption) "
        f"× {authenticity}% authenticity ⇒ ฿{band.low:,}–฿{band.high:,} per post. "
        f"Edit the CPM to your own rate — this is not a market rate card."
    )
    return RateBasis(median_organic_views=mov, cpm_thb=cpm, authenticity=int(authenticity),
                     videos_sampled=len(kol.videos), band=band, method=method)
