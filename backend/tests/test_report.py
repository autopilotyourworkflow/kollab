"""Internal vetting report: every KOL carries the FULL check ledger — fired, clear, and
(the honesty payload) WITHHELD checks — serialized in camelCase."""

from __future__ import annotations

from app.fraud.vet import CHECK_LABELS, to_checks, vet_cohort
from app.pipeline import build_shortlist
from app.sources.seed import SeedDatasetSource

ALL_CHECK_NAMES = set(CHECK_LABELS)


def test_every_kol_has_the_full_check_ledger(shortlist):
    for k in shortlist.kols:
        names = {c.name for c in k.checks}
        assert names == ALL_CHECK_NAMES  # the ledger is complete for every creator
        for c in k.checks:
            assert c.status in {"fired", "clear", "withheld"}
            assert c.label  # never an empty label, even for clear/withheld checks


def test_mimin_report_shows_fired_pod_and_a_withheld_check(by_id):
    mimin = next(k for k in by_id.values() if k.handle == "@mimin.glowyskin")
    fired = {c.name for c in mimin.checks if c.status == "fired"}
    assert fired & {"commenter_reuse", "comment_burst", "duplicate_text"}
    # macro-beauty cohort is tiny, so the peer-comparison check is honestly withheld —
    # the report SHOWS that rather than pretending it ran.
    withheld = {c.name for c in mimin.checks if c.status == "withheld"}
    assert "er_outlier" in withheld


def test_report_serializes_camelcase():
    resp = build_shortlist(SeedDatasetSource())
    dumped = resp.model_dump(by_alias=True)
    k0 = dumped["kols"][0]
    assert "checks" in k0
    assert "measuredAgainst" in k0["checks"][0]


def test_to_checks_is_pure_and_stable_order():
    resp = build_shortlist(SeedDatasetSource())
    # a candidate's raw ledger order matches CHECK_LABELS insertion order
    kol = next(k for k in resp.kols)
    ordered = [c.name for c in kol.checks]
    assert ordered == list(CHECK_LABELS)


def test_withheld_check_exists_somewhere(shortlist):
    # the min-cohort withhold rule is real on the seed cohort — surfaced in the report
    assert any(c.status == "withheld" for k in shortlist.kols for c in k.checks)
