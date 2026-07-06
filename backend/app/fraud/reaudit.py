"""Delivered-post authenticity RE-AUDIT.

A creator can vet clean pre-booking and then buy engagement for the sponsored post. This
re-runs the SAME structural detectors (vet_kol) on the creator's ACTUAL delivered post and
diffs the result against the pre-booking authenticity — zero new judgment logic, so the
re-audit is exactly as trustworthy as the vetting the client already saw.

Honest by construction: a single delivered post has no peer cohort, so the cohort-based
outlier checks WITHHOLD (they can't fire on one post) — but the structural ones (comment
burst, templated pod text, thin commenters, and cross-creator reuse when the persistent
graph knows the accounts) fire on the post's own comments. The verdict only reports what
those measured detectors found.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.fraud.cohort import CohortStats, cohort_key
from app.fraud.signals import build_commenter_index
from app.fraud.vet import _reference_now, to_checks, vet_kol
from app.raw import RawKOL, RawProfile
from app.schemas import DeliveredPostRequest, DeliveryAudit
from app.sources.seed import _gen_clean_comments, _gen_pod_comments, _gen_videos, _rng

_DELIVERED = Path(__file__).resolve().parents[1] / "sources" / "fixtures" / "seed_delivered.json"
_ANCHOR = datetime(2026, 7, 5, 9, 0, 0, tzinfo=timezone.utc)

# Authenticity drop (pre - post) that counts as a real degradation, not noise.
DEGRADE_DROP = 15
# Below this many delivered-post comments the structural detectors can't fire reliably,
# so the re-audit WITHHOLDS ("inconclusive") rather than reporting absence-of-data as clean.
REAUDIT_MIN_COMMENTS = 15


def reaudit_delivered_post(kol: RawKOL, pre_authenticity: int | None = None,
                           graph_store=None) -> DeliveryAudit:
    """Re-vet one delivered post and diff against the pre-booking score. Pure."""
    index = build_commenter_index([kol])
    if graph_store is not None:
        try:
            graph_store.augment(index)  # a known pod is caught even from one post
        except Exception:
            pass
    # One post has no peer cell -> outlier checks withhold honestly.
    cohort = CohortStats(key=cohort_key(kol), n=0, er_median=0, er_iqr=0, er_p25=0,
                         er_p75=0, vtf_median=0, vtf_p10=0, min_n=15)
    now = _reference_now([kol]) or _ANCHOR
    result = vet_kol(kol, cohort, index, now)
    post_auth = result.authenticity_score
    fired = result.risk.level != "clear"

    if len(kol.comments) < REAUDIT_MIN_COMMENTS:
        # Absence of evidence is not evidence of authenticity — withhold, same rule as vetting.
        verdict = "inconclusive"
    elif pre_authenticity is None:
        verdict = "degraded" if fired else "consistent"
    else:
        drop = pre_authenticity - post_auth
        if fired and drop >= DEGRADE_DROP:
            verdict = "degraded"
        elif not fired and pre_authenticity < 60:
            verdict = "cleared"
        else:
            verdict = "consistent"

    labels = ", ".join(s.label for s in result.risk.signals) or "no new signals"
    # The "degraded" note only claims a pre→post diff when a baseline was actually supplied.
    if pre_authenticity is None:
        degraded_note = (f"The delivered post shows engagement patterns ({labels}). No pre-booking "
                         f"baseline was supplied to diff against; post-booking authenticity is "
                         f"{post_auth}. Escalate before the next payment.")
    else:
        degraded_note = (f"The delivered post shows engagement patterns absent pre-booking ({labels}). "
                         f"Authenticity {pre_authenticity}→{post_auth}. Escalate before the next payment.")
    note = {
        "degraded": degraded_note,
        "consistent": f"Delivered post is consistent with the pre-booking vet ({labels}).",
        "cleared": "Delivered post looks clean — the earlier concern did not repeat here.",
        "inconclusive": f"Delivered-post sample too thin to judge ({len(kol.comments)} comments) — withheld.",
    }[verdict]

    return DeliveryAudit(
        handle=kol.profile.unique_id,
        pre_authenticity=pre_authenticity,
        post_authenticity=post_auth,
        verdict=verdict,
        new_signals=result.risk.signals,
        checks=to_checks(result.raw_signals),
        note=note,
    )


# ── demo + live loaders ──────────────────────────────────────────────────────
def _build_delivered_kol(handle: str, d: dict) -> RawKOL:
    """Expand a compact delivered-post descriptor into a RawKOL using the SAME generators
    that build the seed cohort (so the detectors behave identically)."""
    rng = _rng(f"delivered_{handle}")
    aid = handle.lstrip("@")
    vurl = f"https://www.tiktok.com/{handle}/video/delivered"
    videos = _gen_videos(rng, aid, int(d["median_views"]), float(d.get("er", 6.0)),
                         10, _ANCHOR, 3.0)
    if d.get("archetype") == "pod_boosted":
        comments = _gen_pod_comments(rng, aid, vurl, _ANCHOR)
    else:
        comments = _gen_clean_comments(rng, aid, vurl, 100, _ANCHOR)
    profile = RawProfile(author_id=aid, unique_id=handle, nickname=handle,
                         fans=int(d.get("followers", 0)), signature="beauty", region="Bangkok")
    return RawKOL(profile=profile, videos=videos, comments=comments, vertical="beauty", tier="micro")


def load_delivered_fixture(handle: str) -> RawKOL | None:
    """The demo delivered post for a seed creator, or None if we have no fixture."""
    try:
        posts = json.loads(_DELIVERED.read_text(encoding="utf-8")).get("posts", {})
    except Exception:
        return None
    key = handle if handle in posts else "@" + handle.lstrip("@")
    d = posts.get(key)
    return _build_delivered_kol(key, d) if d else None


def build_kol_from_request(req: DeliveredPostRequest) -> RawKOL | None:
    """Assemble a RawKOL from live delivered-post data on the request, or None when the
    request carries no post (caller then falls back to the demo fixture)."""
    if not req.comments and not req.videos:
        return None
    from app.sources.apify import assemble_kol
    profile_item = {"authorMeta": {"name": req.handle.lstrip("@"), "fans": req.followers}}
    return assemble_kol(profile_item, req.videos, req.comments)
