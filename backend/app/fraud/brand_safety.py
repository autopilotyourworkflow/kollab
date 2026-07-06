"""Transparent brand-safety scan — a named, retunable taboo lexicon over the creator's
OWN captions/bio/hashtags, on a SEPARATE axis from fraud risk.

Mirrors the THAI_POD_LEXICON philosophy in app.fraud.signals: a documented, human-
auditable constant, not a black box, and advisory — it routes to human review and
NEVER auto-excludes (an account manager clears or kills, Kollab only surfaces the term).

Two deliberate honesty choices:
  - It reads only what the creator PUBLISHED (their captions/signature/hashtags) — never
    a guess about them — so a flag always cites a real string an AM can go read.
  - Generic skin-whitening / fairness language is a DOCUMENTED OMISSION from this
    universal tier. That vocabulary is culturally normal in Thai beauty; auto-flagging it
    would cry wolf. A brand that won't touch it lists it in its OWN no-go brief
    (a per-brand preference), which is a separate mechanism from this scan.
"""

from __future__ import annotations

from app.raw import RawKOL
from app.schemas import Gate

# (category, (trigger terms...)) — lowercased substring match on the creator's own text.
# Starter set, retunable with the agency and a Thai native; each category is a genuine
# brand-safety hazard, not a stylistic preference.
BRAND_SAFETY_LEXICON: list[tuple[str, tuple[str, ...]]] = [
    ("Unverified medical / efficacy claim",
     ("หายขาด", "รักษาหาย", "หาย 100", "รักษาสิวหาย", "cure acne", "guaranteed results",
      "clinically proven to cure", "100% ได้ผล")),
    ("Gambling promotion",
     ("บาคาร่า", "สล็อต", "แทงบอล", "เว็บพนัน", "baccarat", "casino", "online slot")),
    ("Counterfeit / gray-market goods",
     ("ของปลอม", "แบ่งขายแท้", "หิ้วก๊อป", "replica", "counterfeit", "knockoff")),
    ("Adult / 18+ content",
     ("18+", "adult content", "onlyfans", "sexual content")),
    ("Regulated substance",
     ("กัญชา", "น้ำกระท่อม", "cannabis", "cbd oil", "vape juice")),
]


def _creator_text(kol: RawKOL) -> str:
    parts: list[str] = [kol.profile.signature or ""]
    for v in kol.videos:
        parts.append(v.text or "")
        parts.extend(v.hashtags or [])
    return " ".join(parts).lower()


def scan_brand_safety(kol: RawKOL) -> tuple[str, str] | None:
    """Return (category, matched_term) for the first taboo term found in the creator's
    own published text, or None when clean."""
    text = _creator_text(kol)
    for category, terms in BRAND_SAFETY_LEXICON:
        for term in terms:
            if term.lower() in text:
                return category, term
    return None


def brand_safety_gate(kol: RawKOL, base_status: str, base_note: str | None) -> Gate:
    """Merge the descriptor's brand-safety status with the scan on an INDEPENDENT axis
    (a flag here does not touch fraud risk.level, so recommended/flagged counts are
    unchanged). Human-review wording, offending term always shown."""
    hit = scan_brand_safety(kol)
    if hit is None:
        return Gate(status=base_status, note=base_note)
    category, term = hit
    scan_note = (f"Possible {category.lower()} in the creator's own caption/bio "
                 f"(“{term}”) — routed to human review, not auto-excluded.")
    note = f"{base_note} {scan_note}" if base_note else scan_note
    return Gate(status="flag", note=note)
