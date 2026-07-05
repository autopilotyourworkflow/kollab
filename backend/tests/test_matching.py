"""Scoring, non-ranking audience factor, and the citation validator."""

from __future__ import annotations

from app.fraud.vet import VetResult
from app.matching.rerank import CitationValidator, validate_citations
from app.matching.score import build_factors, fit_score
from app.schemas import Risk
from app.sources.base import Presentation
from tests.conftest import make_kol


def _pres(topic=90, audience=80):
    return Presentation(id="k", name="K", category="Skincare", category_th="สกินแคร์",
                        avatar_initials="KK", avatar_hue=200, topic_score=topic,
                        audience_score=audience, brand_safety_status="clear")


def _clean_vet():
    return VetResult(risk=Risk(level="clear", signals=[]), authenticity_score=90, raw_signals=[])


def test_audience_factor_is_non_ranking():
    factors = build_factors(make_kol(), _pres(), _clean_vet(), last_posted_days_ago=2)
    audience = next(f for f in factors if f.key == "audience")
    assert audience.weight == 0.0 and audience.provenance == "inferred"


def test_fit_score_excludes_zero_weight_audience():
    factors = build_factors(make_kol(), _pres(topic=100, audience=0), _clean_vet(), 2)
    # audience=0 must not drag the score down because its weight is 0
    assert fit_score(factors) >= 90


def test_fit_score_weighted_sum():
    factors = build_factors(make_kol(), _pres(topic=80, audience=50), _clean_vet(), 0)
    # topic 80*.45 + auth 90*.35 + recency 100*.20 all /1.0
    assert 80 <= fit_score(factors) <= 92


def _auth_factor(vet):
    factors = build_factors(make_kol(), _pres(), vet, last_posted_days_ago=2)
    return next(f for f in factors if f.key == "authenticity")


def test_clean_rationale_never_claims_a_withheld_peer_check():
    # Cohort n=1 -> er_outlier withheld -> the rationale must say so, not assert
    # "sits in the healthy band for peers" (a comparison that never ran).
    from app.fraud.signals import SignalResult

    withheld = SignalResult(name="er_outlier", fired=False, level="clear", label="",
                            detail="insufficient baseline — signal withheld",
                            measured_against="lifestyle:macro peers (n=1)", withheld=True)
    vet = VetResult(risk=Risk(level="clear", signals=[]), authenticity_score=100,
                    raw_signals=[withheld])
    rationale = _auth_factor(vet).rationale
    assert "withheld" in rationale
    assert "healthy band" not in rationale


def test_dormancy_only_rationale_is_not_fraud_templated():
    # A stale cadence is not engagement inauthenticity — it must not be wrapped
    # in the "ER is not what it looks like" fraud template.
    from app.fraud.signals import SignalResult

    dormant = SignalResult(name="dormancy", fired=True, level="medium", label="Dormant",
                           detail="Last post 21 days ago — cadence stalled",
                           measured_against="posting timestamps", penalty=0.2)
    vet = VetResult(risk=Risk(level="medium", signals=[]), authenticity_score=80,
                    raw_signals=[dormant])
    rationale = _auth_factor(vet).rationale
    assert "not what it looks like" not in rationale
    assert "cadence" in rationale


def test_validate_citations_flags_uncited():
    allowed = {"dp:er", "dp:cohort_n"}
    ok = validate_citations("ER is high [[dp:er]] vs peers [[dp:cohort_n]]", allowed)
    assert ok.ok is True and not ok.uncited
    bad = validate_citations("cites [[dp:made_up]]", allowed)
    assert bad.ok is False and "dp:made_up" in bad.uncited


def test_citation_validator_withholds_on_persistent_failure():
    v = CitationValidator(allowed_ids={"dp:er"}, max_retries=1)
    text, ok = v.enforce(lambda: "always cites [[dp:ghost]]")
    assert ok is False and "withheld" in text


def test_citation_validator_passes_valid():
    v = CitationValidator(allowed_ids={"dp:er"}, max_retries=1)
    text, ok = v.enforce(lambda: "clean [[dp:er]]")
    assert ok is True and "dp:er" in text
