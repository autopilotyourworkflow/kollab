"""Kollab backend — the judgment layer that turns a licensed KOL feed into a
brand-fit, fraud-screened, ROI-justified shortlist an account manager can defend.

The public/deployed demo runs entirely on curated fixtures (see app.sources.seed),
so a reviewer never hits a rate limit. Apify / Claude / Gemini are swappable
adapters wired behind the same interfaces, enabled only when credentials exist.
"""

__version__ = "0.3.4"
