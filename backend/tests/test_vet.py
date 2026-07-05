"""Vetting orchestration: pod-family dedup, badge ordering, ER suppression."""

from __future__ import annotations

from datetime import timedelta

from app.fraud.vet import vet_cohort
from tests.conftest import BASE, make_cohort, make_comment, make_kol


def _pod_creators(n=4, pool=25):
    ids = [f"pod{i}" for i in range(pool)]
    out = []
    for c in range(n):
        # burst + templated text + shared accounts, all at once
        comments = [make_comment(i, uid=uid, text="ปังมาก", dt=BASE + timedelta(seconds=i))
                    for i, uid in enumerate(ids * 3)]
        out.append(make_kol(author_id=f"cre{c}", comments=comments))
    return out


def test_pod_collapses_to_single_comment_pod_badge():
    creators = _pod_creators()
    result = vet_cohort(creators, creators)["cre0"]
    labels = [s.label for s in result.risk.signals]
    assert result.risk.level == "high"
    assert labels.count("Comment pod") == 1
    # burst/templated are folded into the pod badge, not emitted separately
    assert "Comment burst" not in labels and "Templated comments" not in labels
    # ER outlier is corroboration only — never its own badge when structural fired
    assert "Engagement outlier" not in labels


def test_clean_cohort_is_all_clear():
    peers = make_cohort(20, er_base=6.0)
    vets = vet_cohort(peers, peers)
    assert all(v.risk.level == "clear" and not v.risk.signals for v in vets.values())


def test_authenticity_score_low_for_pod():
    creators = _pod_creators()
    assert vet_cohort(creators, creators)["cre0"].authenticity_score < 30


def test_pod_badge_carries_thai_lexicon_corroboration():
    # "ปังมาก" matches the starter Thai pod-phrase lexicon; the pod badge must
    # surface it as corroboration, explicitly labeled a pattern heuristic.
    creators = _pod_creators()
    pod = next(s for s in vet_cohort(creators, creators)["cre0"].risk.signals
               if s.label == "Comment pod")
    assert "Thai pod phrases" in pod.detail
    assert "pattern heuristic, human-review recommended" in pod.detail
