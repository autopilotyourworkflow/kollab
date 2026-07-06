"""The closed-loop re-rank nudge: neutral learning state at n==0, bounded and labelled
otherwise, and byte-identical to the no-ledger pipeline when nothing is logged."""

from __future__ import annotations

from app.matching.delivery import (
    DELIVERY_NUDGE_CLAMP,
    delivery_adjustment,
)


def test_no_data_is_neutral_learning_state():
    adj, note = delivery_adjustment([])
    assert adj == 0
    assert "log a delivery" in note.lower()  # explicit learning state, not a fabricated number


def test_over_delivery_nudges_up_under_delivery_down():
    up, _ = delivery_adjustment([1.5, 1.6])
    down, _ = delivery_adjustment([0.5, 0.4])
    assert up > 0 and down < 0


def test_nudge_is_hard_clamped():
    huge_up, _ = delivery_adjustment([10.0, 10.0])
    huge_down, _ = delivery_adjustment([0.0, 0.0])
    assert huge_up == DELIVERY_NUDGE_CLAMP
    assert huge_down == -DELIVERY_NUDGE_CLAMP


def test_label_states_the_sample_size():
    _, note = delivery_adjustment([1.2])
    assert "1 logged delivery" in note
    _, note2 = delivery_adjustment([1.2, 0.9])
    assert "2 logged deliveries" in note2


def test_on_target_is_roughly_neutral():
    adj, _ = delivery_adjustment([1.0, 1.0])
    assert adj == 0


def test_pipeline_byte_identical_without_ledger(shortlist):
    # With no DB configured (hermetic tests), the delivery nudge is a no-op: fit scores
    # remain exactly the deterministic factor scores across a clean rebuild.
    from app.pipeline import build_shortlist
    from app.sources.seed import SeedDatasetSource
    by_handle = {k.handle: k.fit_score for k in build_shortlist(SeedDatasetSource()).kols}
    for k in shortlist.kols:
        assert by_handle[k.handle] == k.fit_score
