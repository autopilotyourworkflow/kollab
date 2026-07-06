"""Grounded, citation-validated OUTREACH draft — the second application of the rerank
rigor flex (matching/rerank.py), now aimed at a message SENT to the creator.

Two honesty guarantees:
  1. SAFE ALLOWLIST. The model may only cite a subset of `datapoints_for_kol` — the
     creator's public metrics + topic/recency fit. Every fraud/risk/conflict/rate/score
     data point is EXCLUDED, so the model literally cannot cite (and the validator would
     reject) an internal verdict. A message to a creator can never leak "we think you have
     a comment pod" or a rate we'd pay.
  2. NO PRICE. The prompt forbids any rate/budget, and the deterministic fallback carries
     none — a test asserts no ฿/THB/บาท token appears.

No LLM key (or any failure) -> a labelled deterministic template. Never 503.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from app.config import get_settings
from app.matching.rerank import (
    CitationValidator,
    _strip_citations,
    datapoints_for_kol,
    validate_citations,
)
from app.schemas import ClientBrief, Kol, OutreachDraft

# Data-point ids the outreach message may NEVER reference (internal verdicts / price / score).
_EXCLUDE_PREFIXES = (
    "dp:risk", "dp:signal:", "dp:conflict", "dp:brand_safety", "dp:fit",
    "dp:factor:authenticity", "dp:factor:audience",
)


def outreach_datapoints(kol: Kol) -> dict[str, str]:
    """The SAFE subset of the KOL's data points — public metrics + topic/recency fit only."""
    dp = datapoints_for_kol(kol)
    return {k: v for k, v in dp.items() if not any(k.startswith(p) for p in _EXCLUDE_PREFIXES)}


_PROMPT = """You are an influencer-marketing manager writing a warm, professional FIRST-CONTACT message to a Thai TikTok creator, on behalf of a brand, to open a paid-collaboration conversation.

BRAND: {brand} — {category}. Target audience: {audience}.
CREATOR: {handle} ({name}), {creator_category}.

DATA POINTS YOU MAY CITE (the ONLY facts about the creator you may use):
{dp_lines}

Write 2-3 sentences in English and the same message in natural, casual-professional Thai. Reference at least one data point with a citation marker in double brackets, e.g. "your ~X views a post [[dp:median_views]]". Do NOT mention any internal assessment, risk, authenticity, fraud, or score. Do NOT state or imply any price, rate, budget, or fee. Be genuine and specific, not salesy.

Return STRICT JSON only: {{"en": "...", "th": "..."}}"""


def deterministic_outreach(kol: Kol, brief: ClientBrief) -> tuple[str, str]:
    """Keyless fallback: a real, sendable bilingual draft grounded in one public metric,
    with no internal assessment and no price."""
    en = (f"Hi {kol.name}! We're {brief.brand} — we make {brief.category.lower()}, and we love "
          f"how your {kol.category.lower()} content connects with a Thai audience (around "
          f"{kol.median_views:,} views a post). We'd love to explore a paid collaboration — "
          f"could we share a few details?")
    th = (f"สวัสดีค่ะ คุณ{kol.name} เราคือแบรนด์ {brief.brand} ทำเกี่ยวกับ{brief.category} "
          f"ชอบคอนเทนต์สาย{kol.category}ของคุณมากที่เข้าถึงคนดูชาวไทยได้ดี "
          f"(ยอดวิวราว {kol.median_views:,} ต่อโพสต์) เราอยากชวนร่วมงานแบบมีค่าตอบแทน "
          f"ขอส่งรายละเอียดให้พิจารณาได้ไหมคะ")
    return en, th


def _parse_pair(raw: str) -> tuple[str, str]:
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in outreach response")
    data = json.loads(cleaned[start:end + 1])
    en, th = str(data["en"]).strip(), str(data["th"]).strip()
    if not en or not th:
        raise ValueError("empty outreach copy")
    return en, th


def generate_outreach(kol: Kol, brief: ClientBrief,
                      call: Callable[[str], str] | None = None) -> OutreachDraft:
    """Produce a bilingual outreach draft. LLM path (grounded, citation-validated) when a
    key/`call` is available; otherwise a labelled deterministic template. Any failure or a
    ghost citation falls back to the template — never raises, never 503."""
    allowed = outreach_datapoints(kol)
    settings = get_settings()

    if call is None and not (settings.llm_rerank and settings.effective_llm_enabled):
        en, th = deterministic_outreach(kol, brief)
        return OutreachDraft(en=en, th=th, grounded=False, source="template",
                             note="Deterministic draft (no LLM key) — edit before sending.")
    if call is None:
        from app.llm import claude_text  # lazy
        call = claude_text

    prompt = _PROMPT.format(
        brand=brief.brand, category=brief.category, audience=brief.audience,
        handle=kol.handle, name=kol.name, creator_category=kol.category,
        dp_lines="\n".join(f"  [[{k}]] = {v}" for k, v in allowed.items()),
    )
    pair: dict[str, str] = {}

    def produce() -> str:
        en, th = _parse_pair(call(prompt))
        check = validate_citations(en, set(allowed))
        if not check.cited:
            return "[[dp:__needs_citation__]]"  # force a retry via the validator
        pair["en"], pair["th"] = en, th
        return en + "\n" + th

    try:
        _, ok = CitationValidator(set(allowed), max_retries=1).enforce(produce)
    except Exception:
        ok = False
    if ok and pair:
        return OutreachDraft(en=_strip_citations(pair["en"]), th=_strip_citations(pair["th"]),
                             grounded=True, source="llm",
                             note="Grounded in the creator's public metrics; citation-validated.")
    en, th = deterministic_outreach(kol, brief)
    return OutreachDraft(en=en, th=th, grounded=False, source="template",
                         note="LLM draft unavailable or failed citation check — labelled template.")
