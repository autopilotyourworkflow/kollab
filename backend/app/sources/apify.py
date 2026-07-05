"""ApifyAdapter — LIVE public-data sampling (prototyping only).

⚠️  This adapter samples PUBLIC data via Apify actors for prototyping/demonstration.
    It is ONE swappable KOLSource, clearly labeled non-production. The production
    target is a LICENSED feed (Tellscore/AnyMind/TCM) behind this same interface.

Verified actor payloads (pre-flight spike, 2026-07-02):
  - clockworks/tiktok-scraper           $1.70 / 1k   → profile + video fields
  - clockworks/tiktok-comments-scraper  $0.50 / 1k   → per-comment fields

The JSON→RawKOL mappers are pure and unit-tested against the documented actor
payloads. The actor-run loop below is budget-capped end-to-end (it stops fetching
BEFORE the projected spend crosses the cap) and takes an injectable client so the
whole loop is tested against a fake; the first live run against the real actors is
a calibration run (actor input schemas are documented but only output schemas were
spike-verified).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from zlib import crc32

from app.config import PRICE_PER_1K_COMMENTS, PRICE_PER_1K_RESULTS
from app.matching.topic import keyword_topic_score
from app.raw import RawComment, RawKOL, RawProfile, RawVideo
from app.schemas import ClientBrief
from app.sources.base import KOLSource, Presentation

TIKTOK_SCRAPER_ACTOR = "clockworks/tiktok-scraper"
TIKTOK_COMMENTS_ACTOR = "clockworks/tiktok-comments-scraper"


class RunCancelled(Exception):
    """Raised inside the sourcing loop when the user stopped the run. Deliberately NOT
    a RuntimeError, so it bypasses the live-error handling and is recorded as a clean
    'cancelled', not a failure."""

# Tier bands aligned with the seed cohort's labeling (k8 239K = mid, k4 486K = macro).
TIER_MID_MIN = 100_000
TIER_MACRO_MIN = 400_000

# Placeholder vertical taxonomy for the prototyping adapter — production verticals
# come from the licensed feed's own taxonomy, not keyword guessing.
_VERTICAL_KEYWORDS = {
    "beauty": ("skincare", "beauty", "cosmetic", "makeup", "สกินแคร์", "บิวตี้"),
    "food": ("food", "restaurant", "cafe", "snack", "อาหาร", "คาเฟ่"),
}


def _dataset_id(run) -> str | None:
    """Extract the run's default dataset id from either a dict (tests / older
    client) or the apify-client v3 typed `Run` model (snake_case attribute)."""
    if run is None:
        return None
    if isinstance(run, dict):
        return run.get("defaultDatasetId") or run.get("default_dataset_id")
    return getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None)


def infer_tier(fans: int) -> str:
    if fans >= TIER_MACRO_MIN:
        return "macro"
    if fans >= TIER_MID_MIN:
        return "mid"
    return "micro"


def infer_vertical(brief: ClientBrief) -> str:
    text = f"{brief.category} {' '.join(brief.pillars)}".lower()
    for vertical, words in _VERTICAL_KEYWORDS.items():
        if any(w in text for w in words):
            return vertical
    return "lifestyle"


class BudgetMeter:
    """Hard USD cap for one sourcing run. Every fetch is pre-checked: the run stops
    BEFORE the projected spend crosses the cap — a partial-but-honest pull, never a
    surprise bill."""

    def __init__(self, cap_usd: float):
        self.cap_usd = float(cap_usd)
        self.results = 0   # tiktok-scraper items (videos + profile rows)
        self.comments = 0  # comments-scraper items

    @property
    def spent_usd(self) -> float:
        return round(self.results / 1000 * PRICE_PER_1K_RESULTS
                     + self.comments / 1000 * PRICE_PER_1K_COMMENTS, 4)

    def can_afford(self, extra_results: int = 0, extra_comments: int = 0) -> bool:
        projected = ((self.results + extra_results) / 1000 * PRICE_PER_1K_RESULTS
                     + (self.comments + extra_comments) / 1000 * PRICE_PER_1K_COMMENTS)
        return projected <= self.cap_usd


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


def _norm_url(url: str) -> str:
    """Normalize a TikTok post URL so a scraped comment maps back to its video
    (drop query, fragment, and trailing slash — the actor may echo the URL with
    tracking params)."""
    return url.split("?")[0].split("#")[0].rstrip("/")


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
    """Budget-capped live sourcing loop:

      1. search the tiktok-scraper with brief-derived queries → video items
         (each carries its author's profile in `authorMeta`)
      2. group by author, keep the creators with the most on-query videos
      3. per creator (budget permitting), pull a comment sample for their top posts
      4. hand every raw item to the pure mappers above → RawKOL

    `client` is injectable (tests pass a fake mirroring apify_client's surface:
    .actor(id).call(run_input=...) -> {"defaultDatasetId"} and
    .dataset(id).iterate_items()). Commenter-profile second-pass enrichment is
    deliberately NOT pulled here (cost); without it the thin-commenter detector
    withholds rather than guesses — the documented honest behavior.
    """

    name = "apify"

    def __init__(self, token: str | None = None, budget_usd: float = 5.0,
                 client=None, max_creators: int = 12, videos_per_creator: int = 20,
                 comments_per_creator: int = 120, results_per_query: int = 100,
                 exclude_handles: set[str] | None = None, region: str = "TH",
                 cancel_check=None):
        self.token = token
        self.budget = BudgetMeter(budget_usd)
        self._client = client
        self.max_creators = max_creators
        self.videos_per_creator = videos_per_creator
        self.comments_per_creator = comments_per_creator
        self.results_per_query = results_per_query
        # Optional () -> bool the loop polls at phase boundaries; True stops the run.
        # (An external abort of the Apify run makes the blocking search call return so
        # this check is reached quickly after a stop.)
        self.cancel_check = cancel_check
        # ISO country routed via the scraper's proxy so search returns local
        # creators (default Thailand). "None"/"" -> global.
        self.region = (region or "").strip().upper()
        # Expand-run dedup: creators the brand already holds. They are skipped
        # BEFORE any comment spend and their slots fill with NEW creators —
        # a re-run buys new evidence, never the same data twice. (Their video
        # items still appear in the bulk search; that part is not addressable
        # per-author.)
        self.exclude_handles = {h.strip().lstrip("@").lower() for h in (exclude_handles or set())}
        self._brief: ClientBrief | None = None
        self.last_run: dict = {}

    # ── client plumbing ─────────────────────────────────────────────────────
    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.token:
            raise RuntimeError(
                "ApifyAdapter needs APIFY_TOKEN. The credential-free demo uses "
                "SeedDatasetSource; enable Apify only for the recorded live run."
            )
        try:
            from apify_client import ApifyClient  # optional dep: pip install .[live]
        except ImportError as e:
            raise RuntimeError(
                "apify-client not installed — `pip install apify-client` "
                "(or `pip install -e .[live]`) for the live run."
            ) from e
        return ApifyClient(self.token)

    def _run_actor(self, client, actor_id: str, run_input: dict) -> list[dict]:
        run = client.actor(actor_id).call(run_input=run_input)
        dataset_id = _dataset_id(run)
        if not dataset_id:
            return []
        return list(client.dataset(dataset_id).iterate_items())

    def _raise_if_cancelled(self) -> None:
        if self.cancel_check and self.cancel_check():
            raise RunCancelled("run stopped by user")

    # ── the loop ────────────────────────────────────────────────────────────
    def fetch_candidates(self, brief: ClientBrief) -> list[RawKOL]:
        if brief is None:
            raise ValueError("ApifyAdapter needs a ClientBrief to derive search queries.")
        self._brief = brief
        client = self._get_client()

        # 1) search: brief-derived queries -> video items (author profile embedded)
        queries = search_queries_from_brief(brief)
        est_results = self.results_per_query * len(queries)
        if not self.budget.can_afford(extra_results=est_results):
            raise RuntimeError(
                f"Search phase alone (~{est_results} results) would exceed the "
                f"${self.budget.cap_usd:.2f} run budget — raise KOLLAB_RUN_BUDGET_USD "
                f"or narrow the brief."
            )
        search_input: dict = {
            "searchQueries": queries,
            "resultsPerPage": self.results_per_query,
        }
        if self.region and self.region not in ("NONE", "GLOBAL"):
            search_input["proxyCountryCode"] = self.region  # Thai proxy -> Thai results
        video_items = self._run_actor(client, TIKTOK_SCRAPER_ACTOR, search_input)
        self.budget.results += len(video_items)
        self._raise_if_cancelled()  # user stopped during the (slow) search phase

        # 2) group by author; most on-query videos first (relevance proxy)
        by_author: dict[str, list[dict]] = defaultdict(list)
        for item in video_items:
            author_id = str((item.get("authorMeta") or {}).get("id") or "")
            if author_id:
                by_author[author_id].append(item)
        ranked_authors = sorted(by_author, key=lambda a: len(by_author[a]), reverse=True)

        # 3) select creators (Expand-run dedup skips known ones BEFORE any spend so
        #    their slots fill with new ones), then pull comments for ALL of them in a
        #    SINGLE batched actor call. One Apify run instead of one-per-creator is
        #    the wall-time win that lets a live run finish in ~a minute rather than
        #    stacking a container startup per creator.
        vertical = infer_vertical(brief)
        excluded_known = 0
        selected: list[str] = []
        for author_id in ranked_authors:
            if len(selected) >= self.max_creators:
                break
            meta = (by_author[author_id][0].get("authorMeta") or {})
            handle = str(meta.get("name") or "").strip().lstrip("@").lower()
            if handle and handle in self.exclude_handles:
                excluded_known += 1
                continue
            selected.append(author_id)

        # Per creator: top videos + up to 3 post URLs. Budget-gate on the cumulative
        # projected comment volume; stop adding creators before crossing the cap.
        chosen: list[tuple[list[dict], list[str]]] = []
        projected_comments = 0
        partial = False
        for author_id in selected:
            vids = sorted(by_author[author_id],
                          key=lambda v: int((v.get("stats") or v).get("playCount") or 0),
                          reverse=True)[: self.videos_per_creator]
            post_urls = [v.get("webVideoUrl") for v in vids[:3] if v.get("webVideoUrl")]
            want = self.comments_per_creator if post_urls else 0
            if not self.budget.can_afford(extra_comments=projected_comments + want):
                partial = True  # honest partial pull: stop before crossing the cap
                break
            projected_comments += want
            chosen.append((vids, post_urls))

        # One comments-actor run for every selected post, then map each comment back
        # to its creator by the post URL it was scraped from.
        self._raise_if_cancelled()  # user stopped before the comment-sampling spend
        comments_by_url: dict[str, list[dict]] = defaultdict(list)
        all_urls = [u for (_, urls) in chosen for u in urls]
        if all_urls:
            raw_comments = self._run_actor(client, TIKTOK_COMMENTS_ACTOR, {
                "postURLs": all_urls,
                "commentsPerPost": max(1, self.comments_per_creator // 3),
            })
            self.budget.comments += len(raw_comments)
            for c in raw_comments:
                comments_by_url[_norm_url(str(c.get("videoWebUrl") or ""))].append(c)

        kols: list[RawKOL] = []
        for vids, post_urls in chosen:
            comment_items = [c for u in post_urls for c in comments_by_url.get(_norm_url(u), [])]
            profile_item = vids[0]  # authorMeta rides on every video item
            fans = int(((profile_item.get("authorMeta") or {}).get("fans")) or 0)
            kols.append(assemble_kol(profile_item, vids, comment_items,
                                     vertical=vertical, tier=infer_tier(fans)))

        self.last_run = {
            "queries": queries,
            "region": self.region or "global",
            "creators": len(kols),
            "excluded_known": excluded_known,
            "results": self.budget.results,
            "comments": self.budget.comments,
            "spent_usd": self.budget.spent_usd,
            "cap_usd": self.budget.cap_usd,
            "partial": partial or len(ranked_authors) - excluded_known > self.max_creators,
        }
        return kols

    def presentation(self, kol: RawKOL) -> Presentation:
        handle = kol.profile.unique_id.lstrip("@")
        initials = (handle[:2] or "kk").upper()
        topic, topic_rationale = (keyword_topic_score(self._brief, kol)
                                  if self._brief else (0, None))
        return Presentation(
            id=kol.profile.author_id or handle,
            name=kol.profile.nickname or handle,
            category=kol.profile.signature[:32] or "Creator",
            category_th="",
            avatar_initials=initials,
            avatar_hue=crc32(handle.encode()) % 360,
            topic_score=topic,           # deterministic lexical fallback; LLM rerank refines
            topic_rationale=topic_rationale,
            audience_score=0,            # advisory only; audience inference needs licensed data
            audience_rationale="No audience inference on the public-data path.",
            brand_safety_status="clear",
            conflict_status="clear",
            hitl="pending",
        )


def search_queries_from_brief(brief: ClientBrief, max_queries: int = 3) -> list[str]:
    """Brief -> a few short TikTok search queries: the category head plus the most
    concrete pillars. Deliberately simple and inspectable — query strategy is a
    calibration lever for the live run, not hidden magic."""
    queries: list[str] = []
    head = brief.category.split("/")[0].strip().lower()
    if head:
        queries.append(head)
    for pillar in brief.pillars:
        p = pillar.strip().lower()
        if p and p not in queries:
            queries.append(p)
        if len(queries) >= max_queries:
            break
    return queries[:max_queries] or ["skincare"]
