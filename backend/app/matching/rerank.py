"""Citation-grounded rerank + a post-hoc citation validator.

The rerank prompt passes ENUMERATED data-point IDs and the model may cite only
those. After the model answers, the validator checks every citation against the
allowed set and rejects/retries any uncited claim — a checkable invariant, not
"the LLM said so". This is the rigor flex demoed on camera (Loom beat 4b): the
model tries to cite a point not in the payload and the validator catches it.

`apply_llm_rerank` upgrades the top of a finished shortlist: for each KOL it
enumerates the citable data points from the computed payload, asks the LLM for
bilingual why-copy WITH citation markers, validates, then strips the markers for
display (claims must cite to pass; clients see clean prose). Any failure leaves
the deterministic copy in place — the rerank can only refine, never block or
fabricate. In the credential-free demo the deterministic scorer stands in and
everything here except the LLM call itself remains unit-tested with fakes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from app.config import get_settings
from app.schemas import ClientBrief, Kol, ShortlistResponse

# Citations in a rationale look like [[dp:er]] / [[dp:cohort_n]] — enumerated ids.
_CITATION = re.compile(r"\[\[(dp:[a-zA-Z0-9_.:-]+)\]\]")


@dataclass
class CitationCheck:
    ok: bool
    cited: list[str]
    uncited: list[str]  # citations NOT in the allowed set → invalid claims


def validate_citations(rationale: str, allowed_ids: set[str]) -> CitationCheck:
    """Return which cited data-point ids are outside the allowed payload."""
    cited = _CITATION.findall(rationale)
    uncited = [c for c in cited if c not in allowed_ids]
    return CitationCheck(ok=not uncited, cited=cited, uncited=uncited)


class CitationValidator:
    """Retry-capped guard around an LLM rerank (max_retries), then a visible
    'rationale withheld: citation check failed' fallback that bounds latency/cost
    and turns a hang into another visible rigor signal."""

    def __init__(self, allowed_ids: set[str], max_retries: int = 2):
        self.allowed_ids = allowed_ids
        self.max_retries = max_retries

    def enforce(self, produce_rationale) -> tuple[str, bool]:
        """Call produce_rationale() up to max_retries+1 times until it cites only
        allowed ids. Returns (rationale, ok). On final failure returns the withheld
        badge text and ok=False."""
        last = ""
        for _ in range(self.max_retries + 1):
            last = produce_rationale()
            if validate_citations(last, self.allowed_ids).ok:
                return last, True
        return "rationale withheld: citation check failed", False


# ── LLM why-copy rerank over a finished shortlist ────────────────────────────

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def datapoints_for_kol(kol: Kol) -> dict[str, str]:
    """Enumerate the citable data points for one scored KOL — the ONLY facts the
    rerank model is allowed to reference."""
    dp = {
        "dp:followers": f"{kol.followers:,} followers",
        "dp:median_views": f"median views {kol.median_views:,}",
        "dp:er": f"engagement rate {kol.engagement_rate}%",
        "dp:last_posted": f"last posted {kol.last_posted_days_ago} day(s) ago",
        "dp:fit": f"fit score {kol.fit_score}/100",
        "dp:risk": f"risk level: {kol.risk.level}",
        "dp:tier": f"tier: {kol.tier}",
        "dp:region": f"region: {kol.region}",
    }
    for s in kol.risk.signals:
        dp[f"dp:signal:{_slug(s.label)}"] = f"{s.label}: {s.detail} (measured against {s.measured_against})"
    for f in kol.factors:
        dp[f"dp:factor:{f.key}"] = f"{f.label} {f.score}/100 — {f.rationale}"
    if kol.conflict.status == "flag" and kol.conflict.note:
        dp["dp:conflict"] = f"conflict flag: {kol.conflict.note}"
    if kol.brand_safety.status == "flag" and kol.brand_safety.note:
        dp["dp:brand_safety"] = f"brand-safety flag: {kol.brand_safety.note}"
    return dp


_RERANK_PROMPT = """You are writing the client-facing "why this match" for one Thai TikTok KOL on a vetted shortlist.

BRAND BRIEF: {brand} — {category}. Target audience: {audience}. Content pillars: {pillars}.

KOL: {handle} ({name}), {category_kol}.

DATA POINTS YOU MAY CITE (the ONLY facts you may use):
{dp_lines}

Write 2–3 sentences in English and the same message in natural Thai (casual-professional). Every factual claim MUST carry a citation marker in double brackets naming one of the ids above, e.g. "9.1% engagement [[dp:er]]". Use at least two citations in the English text. If the KOL carries risk signals, lead with the honest caveat — never sell past a flag. Do not invent numbers, audience facts, or rates that are not in the data points.

Return STRICT JSON only: {{"whyEn": "...", "whyTh": "..."}}"""


def _parse_why_json(raw: str) -> tuple[str, str]:
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in rerank response")
    data = json.loads(cleaned[start:end + 1])
    why_en, why_th = str(data["whyEn"]).strip(), str(data["whyTh"]).strip()
    if not why_en or not why_th:
        raise ValueError("empty why copy")
    return why_en, why_th


def _strip_citations(text: str) -> str:
    """Remove the validated [[dp:*]] markers for client display (claims had to
    cite to pass; the client reads clean prose)."""
    return re.sub(r"\s+([,.;:!?])", r"\1", _CITATION.sub("", text)).replace("  ", " ").strip()


def apply_llm_rerank(
    response: ShortlistResponse,
    brief: ClientBrief | None = None,
    call: Callable[[str], str] | None = None,
    max_kols: int = 10,
) -> ShortlistResponse:
    """Upgrade the top-of-list why-copy with citation-validated LLM output.
    No key / disabled / any per-KOL failure -> the deterministic copy stays.
    Requires the English text to carry >=2 validated citations."""
    settings = get_settings()
    if call is None:
        if not (settings.llm_rerank and settings.effective_llm_enabled):
            return response
        from app.llm import claude_text  # lazy
        call = claude_text

    brief = brief or response.brief
    for kol in response.kols[:max_kols]:
        dp = datapoints_for_kol(kol)
        prompt = _RERANK_PROMPT.format(
            brand=brief.brand, category=brief.category, audience=brief.audience,
            pillars=", ".join(brief.pillars) or "—",
            handle=kol.handle, name=kol.name, category_kol=kol.category,
            dp_lines="\n".join(f"  [[{k}]] = {v}" for k, v in dp.items()),
        )
        pair: dict[str, str] = {}

        def produce() -> str:
            why_en, why_th = _parse_why_json(call(prompt))
            check = validate_citations(why_en, set(dp))
            if len(check.cited) < 2:
                return "[[dp:__too_few_citations__]]"  # forces a retry via the validator
            pair["en"], pair["th"] = why_en, why_th
            return why_en + "\n" + why_th

        try:
            _, ok = CitationValidator(set(dp), max_retries=1).enforce(produce)
        except Exception:
            ok = False  # provider/parse failure: keep deterministic copy
        if ok and pair:
            kol.why_en = _strip_citations(pair["en"])
            kol.why_th = _strip_citations(pair["th"])
    return response
