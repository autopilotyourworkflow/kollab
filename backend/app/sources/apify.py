"""ApifyAdapter — LIVE public-data sampling (prototyping only).

⚠️  This adapter samples PUBLIC data via Apify actors for prototyping/demonstration.
    It is ONE swappable KOLSource, clearly labeled non-production. The production
    target is a LICENSED feed (Tellscore/AnyMind/TCM) behind this same interface.

Verified actor payloads (pre-flight spike, 2026-07-02):
  - clockworks/tiktok-scraper           $1.70 / 1k   → profile + video fields
  - clockworks/tiktok-comments-scraper  $0.50 / 1k   → per-comment fields

The JSON→RawKOL mappers below are pure and unit-tested against the documented actor
payloads. The actor-run loop itself is NOT wired in this build (roadmap — it lands
with the recorded live run): fetch_candidates raises a clear error rather than
pretending, and the API turns that into a 503.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zlib import crc32

from app.raw import RawComment, RawKOL, RawProfile, RawVideo
from app.schemas import ClientBrief
from app.sources.base import KOLSource, Presentation

TIKTOK_SCRAPER_ACTOR = "clockworks/tiktok-scraper"
TIKTOK_COMMENTS_ACTOR = "clockworks/tiktok-comments-scraper"


def _to_iso(ts) -> str:
    """Normalize an actor timestamp to ISO 8601, or '' when unusable.

    The actors emit `createTimeISO` (ISO string) and/or `createTime` (unix epoch
    seconds). Every downstream detector parses this field, so the mapper either
    produces a valid ISO string or '' — and assemble_kol DROPS ''-stamped items
    rather than letting them crash the time-based detectors."""
    if ts is None or ts == "":
        return ""
    if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    return str(ts)


# ── Pure mappers (actor JSON → our boundary model) ──────────────────────────
def parse_profile_item(item: dict) -> RawProfile:
    """Map a clockworks/tiktok-scraper profile item to RawProfile."""
    meta = item.get("authorMeta", item)
    return RawProfile(
        author_id=str(meta.get("id") or item.get("id") or item.get("authorId") or ""),
        unique_id="@" + str(meta.get("name") or item.get("uniqueId") or "").lstrip("@"),
        nickname=str(meta.get("nickName") or meta.get("nickname") or item.get("nickname") or ""),
        fans=int(meta.get("fans") or item.get("fans") or 0),
        following=int(meta.get("following") or item.get("following") or 0),
        video_count=int(meta.get("video") or item.get("videoCount") or 0),
        verified=bool(meta.get("verified") or item.get("verified") or False),
        signature=str(meta.get("signature") or item.get("signature") or ""),
        region=str(meta.get("region") or item.get("region") or "Unknown"),
    )


def parse_video_item(item: dict) -> RawVideo:
    """Map a clockworks/tiktok-scraper video item to RawVideo."""
    stats = item.get("stats", item)
    return RawVideo(
        video_id=str(item.get("id") or item.get("videoId") or ""),
        play_count=int(stats.get("playCount") or 0),
        digg_count=int(stats.get("diggCount") or 0),
        comment_count=int(stats.get("commentCount") or 0),
        share_count=int(stats.get("shareCount") or 0),
        collect_count=int(stats.get("collectCount") or 0),
        create_time_iso=_to_iso(item.get("createTimeISO") or item.get("createTime")),
        text=str(item.get("text") or ""),
        hashtags=[h.get("name", h) if isinstance(h, dict) else h for h in item.get("hashtags", [])],
    )


def parse_comment_item(item: dict) -> RawComment:
    """Map a clockworks/tiktok-comments-scraper comment item to RawComment."""
    return RawComment(
        cid=str(item.get("cid") or item.get("id") or ""),
        uid=str(item.get("uid") or item.get("uniqueId") or ""),
        unique_id="@" + str(item.get("uniqueId") or "").lstrip("@"),
        text=str(item.get("text") or ""),
        digg_count=int(item.get("diggCount") or 0),
        reply_comment_total=int(item.get("replyCommentTotal") or 0),
        create_time_iso=_to_iso(item.get("createTimeISO") or item.get("createTime")),
        video_web_url=str(item.get("videoWebUrl") or ""),
    )


def assemble_kol(profile_item: dict, video_items: list[dict], comment_items: list[dict],
                 vertical: str = "beauty", tier: str = "micro") -> RawKOL:
    """Combine one profile + its videos + sampled comments into a RawKOL.

    Items without a usable timestamp are dropped here: every downstream detector
    is time-based, so an unstamped item is unusable evidence, not a crash."""
    return RawKOL(
        profile=parse_profile_item(profile_item),
        videos=[v for v in (parse_video_item(i) for i in video_items) if v.create_time_iso],
        comments=[c for c in (parse_comment_item(i) for i in comment_items) if c.create_time_iso],
        vertical=vertical,
        tier=tier,
    )


class ApifyAdapter(KOLSource):
    name = "apify"

    def __init__(self, token: str | None = None):
        self.token = token

    def fetch_candidates(self, brief: ClientBrief) -> list[RawKOL]:
        if not self.token:
            raise RuntimeError(
                "ApifyAdapter needs APIFY_TOKEN. The credential-free demo uses "
                "SeedDatasetSource; enable Apify only for the recorded live run."
            )
        # NOT WIRED IN THIS BUILD (see README roadmap). The actor→RawKOL mappers
        # above are the tested seam; the thin actor-run loop (run the two actors,
        # read dataset items, hand the JSON to the mappers) ships with the recorded
        # live run. The API surfaces this as a clean 503, never a silent fake result.
        raise NotImplementedError(
            "Live Apify sourcing is not wired in this build — the mappers are the "
            "tested seam; the actor-run loop lands with the recorded live run. "
            "The demo runs entirely on SeedDatasetSource."
        )

    def presentation(self, kol: RawKOL) -> Presentation:
        handle = kol.profile.unique_id.lstrip("@")
        initials = (handle[:2] or "kk").upper()
        return Presentation(
            id=kol.profile.author_id or handle,
            name=kol.profile.nickname or handle,
            category=kol.profile.signature[:32] or "Creator",
            category_th="",
            avatar_initials=initials,
            avatar_hue=crc32(handle.encode()) % 360,
            topic_score=0,      # requires the embeddings/LLM rerank path (roadmap)
            audience_score=0,   # advisory; inference is roadmap
            brand_safety_status="clear",
            conflict_status="clear",
            hitl="pending",
        )
