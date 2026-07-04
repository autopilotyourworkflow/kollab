"""Raw ingestion models — shaped to the real Apify actor payloads.

Verified against the actor schemas during the pre-flight data spike (2026-07-02):
  - clockworks/tiktok-scraper          → profile + video fields
  - clockworks/tiktok-comments-scraper → per-comment fields

Keeping these as an explicit boundary type means the fraud/matching layers depend
on OUR model, not on Apify's JSON — so swapping in a licensed feed is a new adapter,
not a rewrite. Field names below trace 1:1 to the documented actor outputs.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel


def parse_iso(ts: str) -> datetime:
    """Parse actor `createTimeISO` (ISO-8601, may end in 'Z') to aware UTC."""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class RawComment(BaseModel):
    """One comment from clockworks/tiktok-comments-scraper ($0.50 / 1k)."""

    cid: str  # comment id
    uid: str  # commenter account id (stable identity for reuse detection)
    unique_id: str  # commenter @handle
    text: str
    digg_count: int = 0  # likes on the comment
    reply_comment_total: int = 0  # replies under it (thread depth proxy)
    create_time_iso: str
    video_web_url: str = ""
    # --- second-pass commenter-profile enrichment (sampled, to control cost) ---
    # Populated only for a sampled subset; None means "not sampled".
    commenter_post_count: int | None = None
    commenter_has_thai_history: bool | None = None


class RawVideo(BaseModel):
    """One video from clockworks/tiktok-scraper ($1.70 / 1k)."""

    video_id: str
    play_count: int
    digg_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    collect_count: int = 0
    create_time_iso: str
    text: str = ""
    hashtags: list[str] = []


class RawProfile(BaseModel):
    """Creator profile from clockworks/tiktok-scraper."""

    author_id: str
    unique_id: str  # @handle
    nickname: str
    fans: int  # followers
    following: int = 0
    video_count: int = 0
    verified: bool = False
    signature: str = ""
    region: str = "Unknown"


class RawKOL(BaseModel):
    """Everything one adapter returns for a single creator: profile + a video
    sample + a comment sample. The unit the fraud/enrichment layers consume."""

    profile: RawProfile
    videos: list[RawVideo] = []
    comments: list[RawComment] = []
    # Demo/label metadata (kept out of production paths; used to seed fixtures
    # and to let the eval harness know the intended archetype).
    vertical: str = "beauty"
    tier: str = "micro"
