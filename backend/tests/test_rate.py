"""Fair-rate estimator: linear in the operator's CPM, discounted by authenticity, built
only from the creator's OWN measured organic reach, withheld when the sample is too thin —
and framed so it can never read as a market rate card."""

from __future__ import annotations

from app.config import DEFAULT_CPM_THB
from app.fraud.cohort import median_views
from app.pricing.rate import RATE_MIN_VIDEOS, fair_rate_band, rate_basis_for

from tests.conftest import make_kol


def test_band_is_linear_in_cpm():
    b1 = fair_rate_band(10_000, 100, 100)
    b2 = fair_rate_band(10_000, 100, 200)
    assert b2.low == 2 * b1.low and b2.high == 2 * b1.high  # double the assumption -> double the band


def test_authenticity_discounts_reach():
    full = fair_rate_band(10_000, 100, 150)
    half = fair_rate_band(10_000, 50, 150)
    assert half.high == round(full.high * 0.5)  # 50% authenticity halves the estimate
    zero = fair_rate_band(10_000, 0, 150)
    assert zero.low == 0 and zero.high == 0     # reach assessed non-organic -> ~0


def test_low_never_exceeds_high():
    b = fair_rate_band(12_345, 73, 150)
    assert b.low <= b.high


def test_uses_outlier_excluded_organic_median():
    kol = make_kol(median_views=50_000, n_videos=20)
    basis = rate_basis_for(kol, 90)
    assert basis is not None
    assert basis.median_organic_views == int(median_views(kol))  # boosted/outlier posts excluded


def test_withholds_when_too_few_videos():
    assert rate_basis_for(make_kol(n_videos=RATE_MIN_VIDEOS - 1), 80) is None
    assert rate_basis_for(make_kol(n_videos=RATE_MIN_VIDEOS), 80) is not None


def test_default_cpm_used_when_unspecified():
    basis = rate_basis_for(make_kol(n_videos=20), 100)
    assert basis.cpm_thb == DEFAULT_CPM_THB


def test_method_string_disclaims_market_rate():
    basis = rate_basis_for(make_kol(n_videos=20), 100)
    m = basis.method.lower()
    assert "not a market rate" in m and "your assumption" in m


# ── end-to-end on the seed cohort ────────────────────────────────────────────
def test_pipeline_populates_rate_basis(by_id):
    ploy = next(k for k in by_id.values() if k.handle == "@ploy.skinnote")
    assert ploy.rate_basis is not None
    assert ploy.est_rate_thb == ploy.rate_basis.band
    assert ploy.rate_basis.band.low <= ploy.rate_basis.band.high


def test_flagged_creator_rate_is_discounted_vs_clean(by_id):
    ploy = next(k for k in by_id.values() if k.handle == "@ploy.skinnote")     # clean
    mimin = next(k for k in by_id.values() if k.handle == "@mimin.glowyskin")  # comment pod
    assert mimin.rate_basis.authenticity < ploy.rate_basis.authenticity
    # the fraud finding flows straight into the price: a pod creator's reach is worth less
    assert mimin.est_rate_thb.high <= ploy.est_rate_thb.high
