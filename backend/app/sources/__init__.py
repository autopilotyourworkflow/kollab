"""Candidate sourcing behind one swappable interface.

Positioning (locked decision A1): Kollab is the judgment layer on top of *licensed*
KOL data. Apify is ONE adapter for the public-data demo only; the production target
is a licensed feed (Tellscore/AnyMind/TikTok Creator Marketplace) — a new adapter,
not a rewrite, because everything downstream depends on RawKOL, not on any vendor.
"""

from app.sources.apify import ApifyAdapter
from app.sources.base import KOLSource, Presentation
from app.sources.seed import SeedDatasetSource

__all__ = ["KOLSource", "Presentation", "SeedDatasetSource", "ApifyAdapter"]
