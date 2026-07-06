"""Grounded outreach draft: keyless template, citation-validated LLM path, ghost-citation
and failure fall back to the template — and, critically, no fraud verdict or price ever
reaches a message meant for the creator."""

from __future__ import annotations

import json

from app.matching.outreach import generate_outreach, outreach_datapoints
from app.pipeline import build_shortlist
from app.sources.seed import SeedDatasetSource

_SL = build_shortlist(SeedDatasetSource())
FLAGGED = next(k for k in _SL.kols if k.handle == "@mimin.glowyskin")  # comment pod: hardest leak case
CLEAN = next(k for k in _SL.kols if k.handle == "@ploy.skinnote")


def _brief():
    from app.schemas import ClientBrief
    return ClientBrief(brand="Glow Lab", brand_th="โกลว์ แล็บ", category="Skincare",
                       audience="Thai women 22-34", pillars=["Ingredient education"],
                       region="Thailand", website="glowlab.co.th")


PRICE_TOKENS = ("฿", "thb", "บาท", "baht", "$")
LEAK_TOKENS = ("pod", "fraud", "bought", "authenticity", "risk", "fake", "flag")


def test_allowlist_excludes_fraud_and_rate_datapoints():
    dp = outreach_datapoints(FLAGGED)
    assert dp  # some safe points remain
    for key in dp:
        assert not key.startswith(("dp:risk", "dp:signal:", "dp:conflict", "dp:fit"))
    # even for a comment-pod creator, no signal id is exposed to the drafter
    assert not any("signal" in k for k in dp)


def test_keyless_template_has_no_price_or_verdict():
    draft = generate_outreach(FLAGGED, _brief(), call=None)  # no key -> deterministic
    assert draft.source == "template" and draft.grounded is False
    blob = (draft.en + " " + draft.th).lower()
    assert not any(t in blob for t in PRICE_TOKENS)
    assert not any(t in blob for t in LEAK_TOKENS)


def test_llm_path_grounds_and_validates():
    def fake(_prompt):
        return json.dumps({"en": "Hi! Love your ~88,700 views a post [[dp:median_views]] — collab?",
                           "th": "สวัสดีค่ะ ชอบยอดวิวของคุณมากค่ะ"})
    draft = generate_outreach(CLEAN, _brief(), call=fake)
    assert draft.grounded is True and draft.source == "llm"
    assert "[[dp:" not in draft.en  # markers stripped for display


def test_ghost_citation_falls_back_to_template():
    def fake(_prompt):
        # cites a data point that is NOT in the safe allowlist (a fraud verdict) -> rejected
        return json.dumps({"en": "You have a comment pod [[dp:signal:comment_pod]].",
                           "th": "..."})
    draft = generate_outreach(FLAGGED, _brief(), call=fake)
    assert draft.source == "template" and draft.grounded is False


def test_llm_exception_falls_back_to_template():
    def boom(_prompt):
        raise RuntimeError("provider down")
    draft = generate_outreach(CLEAN, _brief(), call=boom)
    assert draft.source == "template"


def test_uncited_llm_output_falls_back():
    def fake(_prompt):
        return json.dumps({"en": "Hey, want to collab?", "th": "อยากร่วมงานไหมคะ"})  # no citation
    draft = generate_outreach(CLEAN, _brief(), call=fake)
    assert draft.source == "template"  # citation required


# ── endpoint ─────────────────────────────────────────────────────────────────
def test_outreach_endpoint_never_503():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    res = client.post("/api/outreach", json={
        "kol": json.loads(CLEAN.model_dump_json(by_alias=True)),
        "brief": json.loads(_brief().model_dump_json(by_alias=True)),
    })
    assert res.status_code == 200
    assert res.json()["source"] in ("llm", "template")
