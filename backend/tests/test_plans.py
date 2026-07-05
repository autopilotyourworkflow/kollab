"""Run-depth plans: estimate math, cap policy, custom bounds, and byte-parity
with the JSON the frontend renders (so UI numbers can never drift)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import PRICE_PER_1K_COMMENTS, PRICE_PER_1K_RESULTS
from app.main import app
from app.sources.plans import CAP_HEADROOM, PRESETS, public_payload, resolve_plan

client = TestClient(app)
FRONTEND_COPY = Path(__file__).resolve().parents[2] / "frontend" / "src" / "data" / "run-plans.json"


def test_estimates_derive_from_verified_prices():
    p = PRESETS["standard"]
    expected = round(3 * p.results_per_query / 1000 * PRICE_PER_1K_RESULTS
                     + p.max_creators * p.comments_per_creator / 1000 * PRICE_PER_1K_COMMENTS, 2)
    assert p.est_usd == expected
    # cap = estimate + headroom, rounded UP to $0.25 — never below the estimate
    for plan in PRESETS.values():
        assert plan.cap_usd >= plan.est_usd
        assert plan.cap_usd <= plan.est_usd * CAP_HEADROOM + 0.25


def test_depth_ordering_costs_more_for_more_evidence():
    assert PRESETS["scan"].est_usd < PRESETS["standard"].est_usd < PRESETS["deep"].est_usd
    assert PRESETS["deep"].max_creators > PRESETS["standard"].max_creators


def test_resolve_plan_rejects_unknown_preset():
    with pytest.raises(ValueError, match="Unknown preset"):
        resolve_plan("turbo")


def test_resolve_plan_custom_overrides_are_bounded():
    plan = resolve_plan("standard", creators=1000, comments=5)
    assert plan.key == "custom"
    assert plan.max_creators == 100   # ceiling
    assert plan.comments_per_creator == 20  # floor
    assert "n=15" in plan.note        # the withhold rule is not configurable


def test_frontend_copy_matches_backend():
    committed = json.loads(FRONTEND_COPY.read_text(encoding="utf-8"))
    assert committed == public_payload(), (
        "frontend/src/data/run-plans.json is stale — regenerate it from "
        "app.sources.plans.public_payload() (see plans.py docstring)."
    )


def test_run_plans_endpoint():
    r = client.get("/api/run-plans")
    assert r.status_code == 200
    body = r.json()
    assert {p["key"] for p in body["presets"]} == {"scan", "standard", "deep"}
    assert all(p["estUsd"] > 0 and p["capUsd"] >= p["estUsd"] for p in body["presets"])


def test_post_shortlist_rejects_unknown_preset(monkeypatch):
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.setenv("APIFY_TOKEN", "dummy")
    brief = {
        "brand": "Test", "brandTh": "เทสต์", "category": "Skincare",
        "audience": "Thai women", "pillars": ["a"], "region": "BKK", "website": "x.co",
    }
    r = client.post("/api/shortlist?preset=turbo", json=brief)
    assert r.status_code == 400
    assert "Unknown preset" in r.json()["detail"]
