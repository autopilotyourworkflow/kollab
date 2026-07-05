"""Bring-your-own-key: per-request credential override, the shared-key kill switch,
the Apify credit meter, and the secret-safety invariants (a pasted key is used for
the one request and never persisted, logged, or returned)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import (
    get_settings,
    request_override_present,
    reset_request_credentials,
    set_request_credentials,
)
from app.credit import fetch_apify_credit, parse_apify_limits
from app.main import app

client = TestClient(app)


# ── effective-key resolution: request key > shared operator key > nothing ─────
def test_request_key_overrides_operator_key(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "operator-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "operator-claude")
    tok = set_request_credentials("visitor-token", "visitor-claude")
    try:
        s = get_settings()
        assert s.effective_apify_token == "visitor-token"
        assert s.effective_anthropic_api_key == "visitor-claude"
        assert request_override_present("apify_token") is True
    finally:
        reset_request_credentials(tok)
    # after reset, the override is gone -> operator key resolves again
    assert get_settings().effective_apify_token == "operator-token"
    assert request_override_present("apify_token") is False


def test_operator_key_is_the_shared_fallback_when_no_request_key(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "operator-token")
    monkeypatch.setenv("KOLLAB_SHARED_KEY", "1")
    tok = set_request_credentials(None, None)  # visitor pasted nothing
    try:
        assert get_settings().effective_apify_token == "operator-token"
    finally:
        reset_request_credentials(tok)


def test_kill_switch_withholds_operator_key(monkeypatch):
    # KOLLAB_SHARED_KEY=0 -> the operator stops spending their own credit: a request
    # with no key of its own resolves to nothing (live run will 503), but a request
    # that brings its OWN key still works.
    monkeypatch.setenv("APIFY_TOKEN", "operator-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "operator-claude")
    monkeypatch.setenv("GEMINI_API_KEY", "operator-gemini")
    monkeypatch.setenv("KOLLAB_SHARED_KEY", "0")

    tok = set_request_credentials(None, None)
    try:
        s = get_settings()
        assert s.effective_apify_token is None
        assert s.effective_anthropic_api_key is None
        assert s.effective_gemini_api_key is None
        assert s.effective_apify_enabled is False
        assert s.effective_llm_enabled is False
    finally:
        reset_request_credentials(tok)

    tok = set_request_credentials("visitor-token", "visitor-claude")
    try:
        s = get_settings()
        assert s.effective_apify_token == "visitor-token"
        assert s.effective_anthropic_api_key == "visitor-claude"
        assert s.effective_apify_enabled is True
    finally:
        reset_request_credentials(tok)


def test_blank_header_values_do_not_count_as_an_override(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "operator-token")
    tok = set_request_credentials("   ", "")  # whitespace/empty -> treated as absent
    try:
        assert request_override_present("apify_token") is False
        assert get_settings().effective_apify_token == "operator-token"
    finally:
        reset_request_credentials(tok)


# ── Apify credit parser (pure) ────────────────────────────────────────────────
_LIMITS_PAYLOAD = {
    "data": {
        "monthlyUsageCycle": {"startAt": "2026-06-20T00:00:00.000Z",
                              "endAt": "2026-07-19T23:59:59.999Z"},
        "limits": {"maxMonthlyUsageUsd": 5},
        "current": {"monthlyUsageUsd": 2.192751953771599},
    }
}


def test_parse_apify_limits_computes_remaining():
    m = parse_apify_limits(_LIMITS_PAYLOAD)
    assert m["limitUsd"] == 5.0
    assert m["usedUsd"] == 2.19
    assert m["remainingUsd"] == 2.81
    assert m["cycleEndAt"] == "2026-07-19T23:59:59.999Z"


def test_parse_apify_limits_missing_usage_is_none_not_zero():
    # Free tier can report usage as absent; we must say 'unknown', never imply $0 used.
    m = parse_apify_limits({"data": {"limits": {"maxMonthlyUsageUsd": 5}, "current": {}}})
    assert m["limitUsd"] == 5.0
    assert m["usedUsd"] is None
    assert m["remainingUsd"] is None


def test_parse_apify_limits_clamps_remaining_at_zero():
    m = parse_apify_limits({"data": {"limits": {"maxMonthlyUsageUsd": 5},
                                     "current": {"monthlyUsageUsd": 6.5}}})
    assert m["remainingUsd"] == 0.0


def test_fetch_apify_credit_without_token_never_calls_network():
    # No token -> honest checked=False, no httpx call attempted, no crash.
    out = fetch_apify_credit(None)
    assert out["checked"] is False and out["remainingUsd"] is None
    assert "no Apify key" in out["note"]


# ── endpoint wiring + secret safety ───────────────────────────────────────────
def test_health_reports_shared_key_flag():
    body = client.get("/health").json()
    assert body["shared_key"] is True


def test_credit_endpoint_labels_source_none_when_not_shared(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "operator-token")
    monkeypatch.setenv("KOLLAB_SHARED_KEY", "0")
    body = client.get("/api/credit").json()
    assert body["sharedKey"] is False
    assert body["apify"]["source"] == "none"
    assert body["apify"]["hasKey"] is False  # operator key withheld, none supplied
    # never returns any token value anywhere in the payload
    assert "operator-token" not in repr(body)


def test_credit_endpoint_labels_source_user_for_a_pasted_key(monkeypatch):
    # A visitor key rides the header; the meter labels it 'user'. Stub the live
    # Apify call (hermetic: no network) but assert the endpoint handed it the
    # VISITOR's token, and that the token never appears in the response body.
    import app.main as main_mod

    seen = {}

    def fake_fetch(token, *a, **k):
        seen["token"] = token
        return {"limitUsd": 5.0, "usedUsd": 1.0, "remainingUsd": 4.0,
                "cycleEndAt": None, "checked": True, "note": ""}

    monkeypatch.setattr(main_mod, "fetch_apify_credit", fake_fetch)
    body = client.get("/api/credit", headers={"X-Apify-Token": "visitor-xyz"}).json()
    assert seen["token"] == "visitor-xyz"  # ran on the visitor's key
    assert body["apify"]["source"] == "user"
    assert body["apify"]["hasKey"] is True
    assert body["apify"]["remainingUsd"] == 4.0
    assert "visitor-xyz" not in repr(body)


def test_live_source_503_when_no_key_and_sharing_off(monkeypatch):
    monkeypatch.setenv("KOLLAB_SOURCE", "apify")
    monkeypatch.setenv("APIFY_TOKEN", "operator-token")
    monkeypatch.setenv("KOLLAB_SHARED_KEY", "0")
    brief = {"brand": "T", "brandTh": "t", "category": "Skincare",
             "audience": "a", "pillars": ["p"], "region": "BKK", "website": "x.co"}
    r = client.post("/api/shortlist", json=brief)  # no key header, sharing off
    assert r.status_code == 503
    assert "your own Apify key" in r.json()["detail"]


def test_request_key_does_not_leak_across_requests(monkeypatch):
    # After a request that supplied its own key, a subsequent request with no key
    # must NOT still see it (the contextvar is reset in the endpoint's finally).
    import app.main as main_mod

    monkeypatch.setenv("APIFY_TOKEN", "operator-token")
    monkeypatch.setenv("KOLLAB_SHARED_KEY", "1")
    tokens: list[str | None] = []

    def fake_fetch(token, *a, **k):
        tokens.append(token)
        return {"limitUsd": 5.0, "usedUsd": 1.0, "remainingUsd": 4.0,
                "cycleEndAt": None, "checked": True, "note": ""}

    monkeypatch.setattr(main_mod, "fetch_apify_credit", fake_fetch)
    client.get("/api/credit", headers={"X-Apify-Token": "visitor-leak-check"})
    body = client.get("/api/credit").json()  # fresh request, no header
    assert body["apify"]["source"] == "shared"  # back to the operator key, not 'user'
    assert tokens == ["visitor-leak-check", "operator-token"]  # no leak into req 2
    assert "visitor-leak-check" not in repr(body)
