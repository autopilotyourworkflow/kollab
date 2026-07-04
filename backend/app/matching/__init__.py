"""Two-stage explainable match: retrieve (recall) → citation-grounded rerank
(precision). In the credential-free demo, topic relevance is precomputed and the
rerank is deterministic; with keys, Stage B is a temp-0 schema-forced LLM call whose
every citation is checked by the validator in rerank.py."""

from app.matching.score import build_factors, fit_score
from app.matching.rerank import CitationValidator, validate_citations

__all__ = ["build_factors", "fit_score", "CitationValidator", "validate_citations"]
