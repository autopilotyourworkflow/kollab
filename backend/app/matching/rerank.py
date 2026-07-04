"""Citation-grounded rerank + a post-hoc citation validator.

The rerank prompt (LLM path) passes ENUMERATED data-point IDs and may cite only
those. After the model answers, this validator checks every citation against the
allowed set and rejects/retries any uncited claim — a checkable invariant, not
"the LLM said so". This is the rigor flex demoed on camera (Loom beat 4b): the
model tries to cite a point not in the payload and the validator catches it.

In the credential-free demo the deterministic scorer (app.matching.score) stands in
for the LLM, so the pipeline runs with zero keys. The validator itself is pure and
unit-tested regardless of whether an LLM is wired.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
