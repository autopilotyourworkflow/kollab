"""Reference-cohort statistics + the minimum-cohort rule.

Outlier detection is only valid against a peer distribution with enough members.
We deep-sample a few (band x vertical) cells so the hero flags fire where they
matter (e.g. beauty-micro, food-micro at n>=15-20); thin cells are marked low-n
and their outlier signals are withheld rather than false-flagged.

Pure stdlib (statistics) — no numpy — so install stays light and portable.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from app.raw import RawKOL


def median_excluding_outliers(values: list[float]) -> float:
    """Median after dropping self-outliers (> 2x the median) — the creator's typical
    level, so a boosted/atypical post doesn't distort 'normal' reach or engagement."""
    if not values:
        return 0.0
    m = median(values)
    kept = [v for v in values if v <= 2 * m] or list(values)
    return float(median(kept))


def engagement_rate(kol: RawKOL) -> float:
    """Engagement rate (%) = median of per-video (likes+comments+shares)/views.

    Per-video ratio (not a ratio of medians) so a view-spiked post — where both
    views and engagement scale together — doesn't distort the rate. View-normalized,
    so it reflects content performance independent of a possibly-bought follower base.
    """
    if not kol.videos:
        return 0.0
    ratios = [
        100.0 * (v.digg_count + v.comment_count + v.share_count) / max(v.play_count, 1)
        for v in kol.videos
    ]
    return round(median(ratios), 2)


def median_views(kol: RawKOL) -> float:
    """Typical views — excludes the creator's own boosted/spike posts (see the
    boosted-post signal, which surfaces those separately)."""
    return median_excluding_outliers([v.play_count for v in kol.videos]) if kol.videos else 0.0


def view_to_follower(kol: RawKOL) -> float:
    """Median views / followers. A bought-follower base makes this collapse."""
    fans = max(kol.profile.fans, 1)
    return median_views(kol) / fans


def _quantile(values: list[float], q: float) -> float:
    """Linear-interpolation quantile (type-7), stdlib-only."""
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    frac = pos - lo
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * frac


@dataclass(frozen=True)
class CohortStats:
    """Distribution summary for one (band x vertical) peer cell."""

    key: str  # e.g. "beauty:micro"
    n: int
    er_median: float
    er_iqr: float  # p75 - p25
    er_p25: float
    er_p75: float
    vtf_median: float  # view-to-follower median
    vtf_p10: float  # low tail — bought-follower floor
    min_n: int = 15

    @property
    def sufficient(self) -> bool:
        """True once the cell has enough peers for outlier signals to be valid."""
        return self.n >= self.min_n

    @property
    def label(self) -> str:
        return f"{self.key} peers (n={self.n})"

    def er_is_high_outlier(self, er: float, k: float = 1.5) -> bool:
        """ER above p75 + k*IQR — suspiciously hot (pod-inflated), Tukey-style."""
        if not self.sufficient or self.er_iqr <= 0:
            return False
        return er > self.er_p75 + k * self.er_iqr


def build_cohorts(kols: list[RawKOL], min_n: int = 15) -> dict[str, CohortStats]:
    """Group creators into (vertical x tier) cells and summarize each.

    Engagement outliers are measured within a cell. Where a cell is too thin,
    callers fall back to the band level (verticals pooled) or withhold the signal.
    """
    groups: dict[str, list[RawKOL]] = {}
    for k in kols:
        groups.setdefault(f"{k.vertical}:{k.tier}", []).append(k)

    stats: dict[str, CohortStats] = {}
    for key, members in groups.items():
        ers = [engagement_rate(m) for m in members]
        vtfs = [view_to_follower(m) for m in members]
        stats[key] = CohortStats(
            key=key,
            n=len(members),
            er_median=round(median(ers), 2) if ers else 0.0,
            er_iqr=round(_quantile(ers, 0.75) - _quantile(ers, 0.25), 2),
            er_p25=round(_quantile(ers, 0.25), 2),
            er_p75=round(_quantile(ers, 0.75), 2),
            vtf_median=round(median(vtfs), 4) if vtfs else 0.0,
            vtf_p10=round(_quantile(vtfs, 0.10), 4),
            min_n=min_n,
        )
    return stats


def cohort_key(kol: RawKOL) -> str:
    return f"{kol.vertical}:{kol.tier}"
