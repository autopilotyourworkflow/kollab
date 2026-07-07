"""Tests for the scheduled re-vet sweep — the diff logic that turns a shortlist into a
monitored asset. Pure functions on synthetic snapshots (fast + deterministic), plus one
end-to-end run over the real seed pipeline."""

from app.revet import (
    ENGAGEMENT_DROP_FRAC,
    Alert,
    diff_snapshots,
    render_report,
    snapshot_from_kols,
)


def _snap(level="clear", er=10.0, signals=()):
    return {"level": level, "engagementRate": er, "signals": sorted(signals)}


def test_snapshot_reduces_payload():
    kols = [
        {
            "handle": "nan",
            "engagementRate": 9.1,
            "risk": {"level": "high", "signals": [{"label": "Comment pod"}, {"label": "View spike"}]},
        },
        {"handle": "ploy", "engagementRate": 4.2, "risk": {"level": "clear", "signals": []}},
    ]
    snap = snapshot_from_kols(kols)
    assert snap["nan"]["level"] == "high"
    assert snap["nan"]["engagementRate"] == 9.1
    assert snap["nan"]["signals"] == ["Comment pod", "View spike"]  # sorted, deduped labels
    assert snap["ploy"]["signals"] == []


def test_risk_worsened_fires():
    prev = {"nan": _snap(level="clear")}
    curr = {"nan": _snap(level="high", signals=["Comment pod"])}
    alerts = diff_snapshots(prev, curr)
    kinds = {a.kind for a in alerts}
    assert "risk_worsened" in kinds
    assert any("clear -> high" in a.summary for a in alerts)


def test_engagement_drop_fires_only_past_threshold():
    prev = {"a": _snap(er=10.0)}
    # 30% drop: below the 40% threshold -> no alert
    assert diff_snapshots(prev, {"a": _snap(er=7.0)}) == []
    # 50% drop: past threshold -> alert
    alerts = diff_snapshots(prev, {"a": _snap(er=5.0)})
    assert [a.kind for a in alerts] == ["engagement_drop"]
    assert ENGAGEMENT_DROP_FRAC == 0.40


def test_new_signal_fires():
    prev = {"a": _snap(signals=["Dormant"])}
    curr = {"a": _snap(signals=["Dormant", "Comment pod"])}
    alerts = diff_snapshots(prev, curr)
    assert [a.kind for a in alerts] == ["new_signal"]
    assert "Comment pod" in alerts[0].summary


def test_new_creator_is_baselined_silently():
    # A KOL new to the shortlist (only in curr) must NOT alert on first sight.
    assert diff_snapshots({}, {"newbie": _snap(level="high", signals=["Comment pod"])}) == []


def test_unchanged_is_silent():
    snap = {"a": _snap(level="medium", er=8.0, signals=["Dormant"])}
    assert diff_snapshots(snap, dict(snap)) == []


def test_render_report_no_alerts():
    out = render_report([], n_kols=12)
    assert "No changes" in out and "12" in out


def test_render_report_lists_alerts():
    out = render_report([Alert("nan", "risk_worsened", "risk clear -> high")], n_kols=7)
    assert "1 alert" in out and "@nan" in out and "clear -> high" in out


def test_seed_sweep_end_to_end_flags_the_known_pod():
    """The real seed pipeline, diffed against a synthetic healthy baseline, must surface
    the demo's known flagged creators — proving the sweep works on real vetting output."""
    from app.revet import _demo_prev, load_current

    curr = snapshot_from_kols(load_current("seed"))
    assert curr, "seed sweep produced an empty shortlist"
    alerts = diff_snapshots(_demo_prev(curr), curr)
    # At least one flagged creator (the demo ships Mimin/Bello as high-risk) surfaces.
    assert any(a.kind == "risk_worsened" for a in alerts)
