"""Transparent brand-safety scan: fires on the creator's own text, names the term,
routes to human review, stays on a separate axis from fraud risk, and deliberately does
NOT cry wolf on culturally-normal cosmetic language."""

from __future__ import annotations

from app.fraud.brand_safety import brand_safety_gate, scan_brand_safety
from app.pipeline import build_shortlist
from app.sources.seed import SeedDatasetSource

from tests.conftest import make_kol


def _kol(caption: str = ""):
    k = make_kol(author_id="c")
    if caption:
        k.videos[0] = k.videos[0].model_copy(update={"text": caption})
    return k


def test_flags_unverified_medical_claim_and_shows_the_term():
    k = _kol("สูตรนี้รักษาฝ้าหายขาดใน 7 วัน")
    hit = scan_brand_safety(k)
    assert hit is not None
    category, term = hit
    assert "medical" in category.lower()
    gate = brand_safety_gate(k, "clear", None)
    assert gate.status == "flag"
    assert term in (gate.note or "")                       # offending term always shown
    assert "human review" in (gate.note or "").lower()     # advisory, not auto-exclude


def test_gambling_promo_flagged():
    hit = scan_brand_safety(_kol("แถมโค้ดเว็บบาคาร่าให้ด้วย"))
    assert hit is not None and "gambling" in hit[0].lower()


def test_clean_caption_is_clear():
    assert scan_brand_safety(_kol("รีวิวเซรั่มตัวใหม่ เนื้อบางซึมไว")) is None
    assert brand_safety_gate(_kol(), "clear", None).status == "clear"


def test_generic_whitening_is_a_documented_omission():
    # Culturally-normal Thai cosmetic vocabulary is intentionally NOT a universal taboo —
    # a brand that won't touch it lists it in its own no-go brief instead.
    for term in ["ไวท์เทนนิ่ง", "whitening serum", "ผิวขาวใส", "brightening cream"]:
        assert scan_brand_safety(_kol(term)) is None


def test_scan_preserves_an_existing_flag_note():
    gate = brand_safety_gate(_kol("รักษาสิวหาย 100"), "flag", "Existing concern")
    assert gate.status == "flag"
    assert "Existing concern" in (gate.note or "")


def test_seed_brand_safety_is_independent_of_fraud_risk():
    resp = build_shortlist(SeedDatasetSource())
    fah = next(k for k in resp.kols if k.handle == "@fah.glowup")
    assert fah.brand_safety.status == "flag"          # the seed probe fires
    assert "หายขาด" in (fah.brand_safety.note or "")
    assert fah.risk.level == "clear"                  # but fraud risk is untouched
    risk_flagged = [k for k in resp.kols if k.risk.level != "clear"]
    assert resp.flagged == len(risk_flagged)          # counts follow risk, not brand safety
    assert fah not in risk_flagged
