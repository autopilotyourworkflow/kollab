"""Brand DNA extraction: client website → ClientBrief.

Degradation chain (each result names its source, so the UI can badge honestly):

  1. **Claude** — structured-JSON extraction from the fetched page text
  2. **Gemini** — same prompt over REST, used when Claude is unavailable/fails
  3. **rules skeleton** — domain-derived stub, `degraded=True` ("degraded extraction")

Every step is injectable (`fetch_text` / `claude_call` / `gemini_call`), so the whole
chain is tested with fakes; SDK/network imports are lazy, so the credential-free
install needs none of them. An LLM response that fails JSON/schema validation falls
through to the next tier — the chain never fabricates a confident-looking brief.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlparse

from app.config import get_settings
from app.llm import claude_text, gemini_text
from app.schemas import ClientBrief

MAX_SITE_CHARS = 8000
FETCH_TIMEOUT_S = 10.0

_PROMPT = """You are extracting a marketing brief for a Thai influencer campaign from a brand's website text.

Return STRICT JSON only (no prose, no code fence) with exactly these keys:
  "brand"    — the brand name as written on the site
  "brandTh"  — the Thai rendering of the brand name if present on the page, else ""
  "category" — one short line: product category / positioning
  "audience" — one short line describing the target customer, grounded in the page
  "pillars"  — array of 3-5 short content-pillar strings grounded in the page
  "region"   — geographic focus if stated, else ""
  "website"  — "{url}"

Rules: never invent facts that are not supported by the page text; leave a field ""
(or a shorter pillars list) rather than guessing.

PAGE TEXT:
{text}
"""


class _TextExtractor(HTMLParser):
    """Minimal HTML → visible-text extraction (stdlib; no bs4 dependency)."""

    _SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.chunks.append(data.strip())


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    return url


def _fetch_site_text(url: str) -> str:
    import httpx  # lazy: live-path dependency only

    r = httpx.get(
        _normalize_url(url),
        timeout=FETCH_TIMEOUT_S,
        follow_redirects=True,
        headers={"User-Agent": "Kollab/0.1 brand-dna preview (contact via brief owner)"},
    )
    r.raise_for_status()
    parser = _TextExtractor()
    parser.feed(r.text[:500_000])
    text = re.sub(r"\s+", " ", " ".join(parser.chunks))
    return text[:MAX_SITE_CHARS]


def _parse_brief_json(raw: str, website: str) -> ClientBrief:
    """Validate an LLM response into ClientBrief. Raises on any shape violation —
    the caller degrades to the next tier instead of shipping a malformed brief."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in LLM response")
    data = json.loads(cleaned[start:end + 1])
    data.setdefault("website", website)
    data.setdefault("brandTh", "")
    data.setdefault("region", "")
    return ClientBrief.model_validate(data)


def rules_skeleton(url: str) -> ClientBrief:
    """Deterministic last-resort brief: domain-derived, clearly incomplete.
    Everything unknown stays empty — the UI badges this 'degraded extraction'
    and the account manager fills the gaps (their edits persist)."""
    host = urlparse(_normalize_url(url)).netloc or url
    stem = host.removeprefix("www.").split(".")[0]
    brand = re.sub(r"[-_]+", " ", stem).title() or "Unknown brand"
    return ClientBrief(
        brand=brand,
        brand_th="",
        category="Unknown — needs manual review",
        audience="",
        pillars=[],
        region="",
        website=url,
    )


@dataclass
class BrandDnaResult:
    brief: ClientBrief
    degraded: bool
    source: str  # "claude" | "gemini" | "rules"
    note: str = ""


def extract_brand_dna(
    url: str,
    fetch_text: Callable[[str], str] | None = None,
    claude_call: Callable[[str], str] | None = None,
    gemini_call: Callable[[str], str] | None = None,
) -> BrandDnaResult:
    settings = get_settings()

    try:
        text = (fetch_text or _fetch_site_text)(url)
    except Exception as e:  # unreachable site -> honest degraded skeleton
        return BrandDnaResult(rules_skeleton(url), True, "rules", f"site fetch failed: {e}")
    if not text.strip():
        return BrandDnaResult(rules_skeleton(url), True, "rules", "site returned no readable text")

    prompt = _PROMPT.format(url=url, text=text)
    notes: list[str] = []
    tiers: list[tuple[str, Callable[[str], str] | None]] = [
        ("claude", claude_call or (claude_text if settings.effective_anthropic_api_key else None)),
        ("gemini", gemini_call or (gemini_text if settings.effective_gemini_api_key else None)),
    ]
    for name, call in tiers:
        if call is None:
            continue
        try:
            return BrandDnaResult(_parse_brief_json(call(prompt), url), False, name)
        except Exception as e:  # provider or validation failure -> next tier
            notes.append(f"{name}: {e}")

    return BrandDnaResult(
        rules_skeleton(url), True, "rules",
        "; ".join(notes) or "no LLM key configured — rules-based skeleton",
    )
