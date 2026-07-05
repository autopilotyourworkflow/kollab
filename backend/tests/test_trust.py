"""Trust layer: deterministic confidence functions + provenance/advisory wiring."""

from __future__ import annotations

from app.matching.score import WEIGHTS, build_factors
from app.sources.base import Presentation
from app.trust.confidence import (
    audience_confidence,
    authenticity_confidence,
    outlier_confidence,
)
from app.trust.provenance import PROVENANCE_BY_FACTOR, advisory_tag
from tests.conftest import make_kol


def test_authenticity_confidence_scales_with_sample():
    assert authenticity_confidence(0) == 0.0
    assert authenticity_confidence(100, target=200) == 0.5
    assert authenticity_confidence(500, target=200) == 1.0


def test_audience_confidence_capped_because_inferred():
    assert audience_confidence(4, 4) == 0.6  # never full confidence: inferred
    assert audience_confidence(0, 4) == 0.0
    assert audience_confidence(2, 0) == 0.0


def test_outlier_confidence_zero_below_min_n():
    assert outlier_confidence(10, min_n=15) == 0.0  # withheld zone
    assert outlier_confidence(30, min_n=15) == 1.0


def test_advisory_tag_only_for_non_measured():
    assert advisory_tag("measured") is None
    assert "do not quote" in advisory_tag("inferred")


def test_provenance_map_covers_every_ranking_factor():
    assert set(PROVENANCE_BY_FACTOR) == set(WEIGHTS)


def test_audience_factor_rationale_carries_advisory_tag():
    from app.fraud.vet import VetResult
    from app.schemas import Risk

    vet = VetResult(risk=Risk(level="clear", signals=[]), authenticity_score=90, raw_signals=[])
    pres = Presentation(id="k", name="K", category="Skincare", category_th="สกินแคร์",
                        avatar_initials="KK", avatar_hue=200, topic_score=90,
                        audience_score=80, brand_safety_status="clear")
    factors = build_factors(make_kol(), pres, vet, last_posted_days_ago=2)
    audience = next(f for f in factors if f.key == "audience")
    assert audience.provenance == PROVENANCE_BY_FACTOR["audience"]
    assert "do not quote to client as fact" in audience.rationale
