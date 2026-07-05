"""Thin LLM text callers, shared by brand ingest and the rerank path.

Lazy imports: the credential-free install never needs the SDKs. Models come from
Settings (env-overridable). These are deliberately dumb — retries, validation,
and degradation policy live with the callers (ingest/brand_dna, matching/rerank),
where they can be tested with fakes.
"""

from __future__ import annotations

from app.config import get_settings


def claude_text(prompt: str, max_tokens: int = 1200) -> str:
    import anthropic  # lazy: pip install .[live]

    s = get_settings()
    msg = anthropic.Anthropic(api_key=s.anthropic_api_key).messages.create(
        model=s.claude_model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def gemini_text(prompt: str) -> str:
    import httpx  # lazy

    s = get_settings()
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:generateContent",
        params={"key": s.gemini_api_key},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
