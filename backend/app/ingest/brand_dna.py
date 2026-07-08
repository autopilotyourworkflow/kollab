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
  "tone"     — one short line describing the brand's tone / voice, inferred from the copy
  "pillars"  — array of 3-5 short content-pillar strings grounded in the page
  "searchTerms" — array of 3-5 SHORT phrases to search TikTok with to find creators who
      make content for this brand's product category. These are content TOPICS people post
      about (e.g. "thai skincare", "makeup review", "clean beauty", "รีวิวสกินแคร์"), NOT
      the brand's values or slogans. Prefer 2-3 words, mix English and Thai, and lean on
      the product category + audience — never abstract values like "innovation" or "trust".
  "region"   — geographic focus if stated, else ""
  "website"  — "{url}"

Rules: never invent facts that are not supported by the page text; leave a field ""
(or a shorter list) rather than guessing. searchTerms is the exception — always give the
best category-based content topics even if the page is thin, since it drives creator search.

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


def _host_is_public(host: str) -> bool:
    """True only if EVERY resolved IP for `host` is a public, routable address. SSRF guard:
    rejects loopback/private/link-local/reserved/multicast/unspecified targets — including
    127.0.0.1, 10/172.16/192.168, and the cloud-metadata address 169.254.169.254 — so an
    attacker-supplied `website` can't make the server fetch internal services."""
    import ipaddress
    import socket

    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False  # unresolvable -> refuse (fail closed)
    if not infos:
        return False
    for info in infos:
        ip = info[4][0]
        # strip a possible IPv6 zone id (fe80::1%eth0)
        ip = ip.split("%", 1)[0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return False
    return True


def _url_is_safe(url: str) -> bool:
    """http(s) scheme + a public host. Used before any server-side fetch."""
    p = urlparse(_normalize_url(url))
    return p.scheme in ("http", "https") and _host_is_public(p.hostname or "")


class UnsafeFetchError(RuntimeError):
    """The requested URL resolves to a non-public address (SSRF guard tripped)."""


def _fetch_site_text(url: str) -> str:
    import httpx  # lazy: live-path dependency only

    # Follow redirects MANUALLY so every hop is SSRF-checked: a public URL that 30x-redirects
    # to an internal address (127.0.0.1 / 169.254.169.254 / VPC) must not slip past the guard.
    current = _normalize_url(url)
    with httpx.Client(
        timeout=FETCH_TIMEOUT_S,
        follow_redirects=False,
        headers={"User-Agent": "Kollab/0.1 brand-dna preview (contact via brief owner)"},
    ) as client:
        for _hop in range(5):
            if not _url_is_safe(current):
                raise UnsafeFetchError(f"refusing to fetch a non-public address: {current!r}")
            r = client.get(current)
            if r.is_redirect and r.headers.get("location"):
                current = str(r.next_request.url) if r.next_request else r.headers["location"]
                continue
            r.raise_for_status()
            parser = _TextExtractor()
            parser.feed(r.text[:500_000])
            text = re.sub(r"\s+", " ", " ".join(parser.chunks))
            return text[:MAX_SITE_CHARS]
    raise UnsafeFetchError("too many redirects")


READER_TIMEOUT_S = 30.0
READER_MIN_CHARS = 200  # below this the direct read is too thin — try the reader


def _fetch_via_reader(url: str) -> str:
    """Fallback fetch through Jina Reader (r.jina.ai): it renders JS and fetches from its
    own good-reputation IPs, so it reads sites that block or JS-gate a plain server-side
    request from a datacenter — the common failure. No key needed; an optional
    JINA_API_KEY lifts the free rate limit. Returns clean, whitespace-collapsed text."""
    import os

    import httpx  # lazy: live-path dependency only

    # Same SSRF guard as the direct path: never hand an internal address to the reader proxy.
    if not _url_is_safe(url):
        raise UnsafeFetchError(f"refusing to read a non-public address: {url!r}")

    headers = {"X-Return-Format": "text"}
    key = os.getenv("JINA_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    r = httpx.get(
        f"https://r.jina.ai/{_normalize_url(url)}",
        headers=headers,
        timeout=READER_TIMEOUT_S,
        follow_redirects=True,
    )
    r.raise_for_status()
    return re.sub(r"\s+", " ", r.text).strip()[:MAX_SITE_CHARS]


def _read_site(url: str, fetch_text: Callable[[str], str] | None) -> str:
    """Read a site's text: a fast direct request first, then — only on the real path (no
    injected fetcher) — the Jina reader when the direct read is blocked or too thin. Each
    tier is best-effort; a total miss returns '' and the caller degrades honestly."""
    try:
        direct = ((fetch_text or _fetch_site_text)(url) or "").strip()
    except Exception:
        direct = ""
    # Injected fetcher (tests) -> never hit the network; a rich direct read -> use it.
    if fetch_text is not None or len(direct) >= READER_MIN_CHARS:
        return direct
    try:
        reader = _fetch_via_reader(url)
    except Exception:
        reader = ""
    return reader if len(reader) > len(direct) else direct


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
    data.setdefault("tone", "")
    data.setdefault("searchTerms", [])
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
    text: str | None = None,
    fetch_text: Callable[[str], str] | None = None,
    claude_call: Callable[[str], str] | None = None,
    gemini_call: Callable[[str], str] | None = None,
) -> BrandDnaResult:
    """Extract a brief from a client's website, or from `text` supplied directly (the paste
    box / the browser bookmarklet — a real browser reads sites a datacenter fetch can't).
    Fetch chain when no text is given: direct request -> Jina reader -> rules skeleton."""
    settings = get_settings()

    page_text = (text or "").strip()[:MAX_SITE_CHARS] if text and text.strip() else _read_site(url, fetch_text)
    if not page_text.strip():
        return BrandDnaResult(
            rules_skeleton(url), True, "rules",
            "site returned no readable text — paste the page's text or use the Kollab bookmarklet",
        )

    prompt = _PROMPT.format(url=url, text=page_text)
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
