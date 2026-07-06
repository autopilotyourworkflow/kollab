"""End-to-end pipeline: brief + source → enrich → vet → match → rank → shortlist.

Produces exactly the ShortlistResponse the deployed frontend renders. Runs with
zero credentials on SeedDatasetSource; the same code path serves the ApifyAdapter
(or a licensed feed) when a source provides live data.
"""

from __future__ import annotations

from app.config import PRICE_PER_1K_COMMENTS, PRICE_PER_1K_RESULTS
from app.fraud.brand_safety import brand_safety_gate
from app.fraud.cohort import engagement_rate, median_views
from app.fraud.graph import get_graph_store, remember_edges
from app.fraud.vet import _reference_now, to_checks, vet_cohort
from app.matching.score import build_factors, fit_score
from app.pricing.rate import rate_basis_for
from app.raw import RawKOL, parse_iso
from app.schemas import (
    Avatar,
    ClientBrief,
    CostMeter,
    Gate,
    Kol,
    ShortlistResponse,
)
from app.sources.base import KOLSource


def _last_posted_days(kol: RawKOL, now) -> int:
    if not kol.videos:
        return 999
    last = max(parse_iso(v.create_time_iso) for v in kol.videos)
    return max((now - last).days, 0)


def _why(pres, kol: RawKOL, vet, fit: int) -> tuple[str, str]:
    # Curated grounded copy wins when the descriptor provides it (seed mode);
    # the deterministic template below is the credential-free fallback.
    if pres.why_en and pres.why_th:
        return pres.why_en, pres.why_th
    er = engagement_rate(kol)
    fans = kol.profile.fans
    if vet.risk.level != "clear":
        labels = ", ".join(s.label for s in vet.risk.signals)
        lead = vet.risk.signals[0]
        en = (f"Looks appealing — {fans:,} followers, ER {er}% — but Kollab flags {labels}. "
              f"{lead.detail} ({lead.measured_against}). Routed to human review, not auto-excluded.")
        th = (f"ดูน่าสนใจ — ฟอลโล {fans:,} เอนเกจ {er}% — แต่ Kollab จับสัญญาณ {labels} "
              f"ส่งให้คนรีวิว ไม่ตัดออกอัตโนมัติ")
    else:
        en = (f"{pres.name} is a strong, low-risk fit: {pres.category} to a Thai skincare "
              f"audience, with clean engagement (ER {er}%) and healthy reach. Fit {fit}/100.")
        th = (f"{pres.name} เหมาะกับแบรนด์ ความเสี่ยงต่ำ คอนเทนต์ {pres.category} "
              f"เอนเกจสะอาด (ER {er}%) รีชดี คะแนน {fit}/100")
    return en, th


def estimate_cost(candidates: list[RawKOL]) -> CostMeter:
    """Projected cost of pulling this shortlist live via Apify — real arithmetic on
    real data volume, shown to the account manager (fixtures mode does not spend it)."""
    comments = sum(len(k.comments) for k in candidates)
    results = sum(len(k.videos) + 1 for k in candidates)  # +1 profile call per creator
    usd = round(comments / 1000 * PRICE_PER_1K_COMMENTS + results / 1000 * PRICE_PER_1K_RESULTS, 2)
    seconds = round(results * 0.03 + comments * 0.002, 1)
    return CostMeter(usd=usd, seconds=seconds, cache_hit_rate=0.0)


def build_shortlist(
    source: KOLSource,
    brief: ClientBrief | None = None,
    min_n: int = 15,
    degraded: bool = False,
) -> ShortlistResponse:
    if brief is None and hasattr(source, "client_brief"):
        brief = source.client_brief()
    if brief is None:
        raise ValueError("A ClientBrief is required (source provided none).")

    candidates = source.fetch_candidates(brief)
    extra = source.reuse_corpus()
    corpus = candidates + extra
    # Prefer the dataset's own as-of date (deterministic) when the source provides
    # one; otherwise infer "now" from the most recent activity in the corpus.
    now = getattr(source, "as_of", None) or _reference_now(corpus)
    # Persistent cross-run commenter graph (the fraud-recall moat): vet against the
    # accumulated history, then record this run's edges so the next run knows more.
    # Both calls are best-effort and no-op without a store, so the seed path is
    # byte-identical and a DB hiccup never blocks vetting.
    graph_store = get_graph_store()
    vet_map = vet_cohort(candidates, corpus, now=now, min_n=min_n, graph_store=graph_store)

    kols: list[Kol] = []
    for kol in candidates:
        pres = source.presentation(kol)
        vet = vet_map[kol.profile.author_id]
        last_days = _last_posted_days(kol, now)
        factors = build_factors(kol, pres, vet, last_days)
        fit = fit_score(factors)
        why_en, why_th = _why(pres, kol, vet, fit)
        # Fair-rate estimate: the creator's own organic reach × the default CPM
        # assumption × authenticity (the UI rescales the band live as the CPM changes).
        rate_basis = rate_basis_for(kol, vet.authenticity_score)
        kols.append(Kol(
            id=pres.id,
            handle=kol.profile.unique_id,
            name=pres.name,
            avatar=Avatar(initials=pres.avatar_initials, hue=pres.avatar_hue),
            category=pres.category,
            category_th=pres.category_th,
            tier=kol.tier,
            region=kol.profile.region,
            followers=kol.profile.fans,
            median_views=int(median_views(kol)),
            engagement_rate=engagement_rate(kol),
            last_posted_days_ago=last_days,
            fit_score=fit,
            risk=vet.risk,
            # Brand safety is a SEPARATE axis from fraud risk: scan the creator's own
            # captions/bio against the taboo lexicon and merge with the descriptor. A
            # flag here routes to human review and never changes risk.level / counts.
            brand_safety=brand_safety_gate(kol, pres.brand_safety_status, pres.brand_safety_note),
            conflict=Gate(status=pres.conflict_status, note=pres.conflict_note),
            factors=factors,
            why_en=why_en,
            why_th=why_th,
            est_rate_thb=rate_basis.band if rate_basis else None,
            rate_basis=rate_basis,
            hitl=pres.hitl,
            checks=to_checks(vet.raw_signals),  # full ledger for the internal report
        ))

    kols.sort(key=lambda k: k.fit_score, reverse=True)
    recommended = sum(1 for k in kols if k.risk.level == "clear" and k.fit_score >= 70)
    flagged = sum(1 for k in kols if k.risk.level != "clear")
    screened = len(candidates) + len(extra)

    # Record this run's commenter->creator edges so the next run knows more (best-effort,
    # once per identical corpus per process — the moat grows without slowing the demo).
    remember_edges(corpus, source=source.name)

    return ShortlistResponse(
        brief=brief,
        kols=kols,
        screened=screened,
        recommended=recommended,
        flagged=flagged,
        cost=estimate_cost(candidates),
        source=source.name,
        degraded=degraded,
    )
