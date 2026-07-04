"""Provenance tagging. Every derived field is measured / inferred / estimated, and
inferred-audience lines carry an inline "do not quote to client as fact" tag that
travels with the data (and would be inherited by a PDF export)."""

from __future__ import annotations

from app.schemas import Provenance

PROVENANCE_BY_FACTOR: dict[str, Provenance] = {
    "topic": "measured",       # from actual captions/hashtags
    "authenticity": "measured",  # from actual comment/engagement structure
    "recency": "measured",     # from actual post timestamps
    "audience": "inferred",    # inferred from comment-language/content skew
}

_ADVISORY = "inferred, not measured — do not quote to client as fact"


def advisory_tag(provenance: Provenance) -> str | None:
    """Inline tag for anything not directly measured, so an AM can't quote an
    inferred number to a client as fact. None for measured fields."""
    return _ADVISORY if provenance != "measured" else None
