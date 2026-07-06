"""SeedDatasetSource — deterministic curated fixtures.

Expands the compact descriptors in fixtures/seed_cohort.json into full Apify-shaped
RawKOL data (profile + video sample + comment sample) using a per-handle seeded RNG,
so every run is byte-reproducible (no Date.now / no live RNG). The synthetic raw data
is engineered so the STRUCTURAL detectors in app.fraud reproduce the exact story the
deployed UI shows:

  - comment_pod  (Mimin): 41 shared pod accounts commenting across 6 creators (Mimin +
                 5 decoys), a >30-comment burst, templated text, plus a 6.2x view spike.
  - bought_followers (Bello): views collapse to ~2.4% of followers + thin commenters.
  - boosted (Gigi): 2 recent posts at 2.1x her own trailing median.
  - clean: pod-free, varied comments, healthy view-to-follower.

Cohort fillers (clean beauty peers) are added to the vetting corpus ONLY (never the
shortlist) so the hero cohort cells reach n>=15 and outlier signals are valid.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from random import Random
from statistics import median
from zlib import crc32

from app.raw import RawComment, RawKOL, RawProfile, RawVideo, parse_iso
from app.schemas import ClientBrief
from app.sources.base import KOLSource, Presentation

_FIXTURE = Path(__file__).parent / "fixtures" / "seed_cohort.json"

# Shared comment-pod account pool (same identities reused across Mimin + decoys).
POD_POOL = [f"pod_{i:03d}" for i in range(41)]

# Text pools — combinatorial variety for clean creators (so duplicate-text does NOT
# false-fire), tight templated set for pods (so it correctly does).
_CLEAN_A = ["สูตรนี้", "ตัวนี้", "อันนี้", "ผลิตภัณฑ์นี้", "รีวิว", "คลิปนี้", "พี่", "เนื้อ",
            "กลิ่น", "ราคา", "ผิวหนู", "แพ็กเกจ", "เทกซ์เจอร์", "ส่วนผสม", "หลอดนี้", "แบรนด์นี้"]
_CLEAN_B = ["ดีมากเลยค่ะ", "น่าลองมาก", "ใช้แล้วดีไหมคะ", "ขอบคุณสำหรับรีวิวค่ะ", "ราคาเท่าไหร่คะ",
            "ผิวแพ้ง่ายใช้ได้ไหม", "อธิบายละเอียดดี", "ซื้อที่ไหนคะ", "รอโค้ดส่วนลด", "ชอบความจริงใจ",
            "ข้อมูลแน่นมาก", "ตามมาจากคลิปก่อน", "เห็นผลจริงไหมคะ", "อยากได้รีวิวตัวต่อไป", "กดติดตามแล้ว", "เป็นกำลังใจให้ค่ะ"]
_POD_TEXTS = ["สวยมากค่ะ ปัง!", "ตัวแม่ตัวจริง รับทรัพย์", "ว้าวมาก จัดไป", "ของแท้ แอดมินทักแชท"]
_BOT_TEXTS = ["nice", "👍", "cool", "😍😍", "beautiful", "wow", "good", "🔥", "love it", "follow back"]


def _iso(dt) -> str:
    return dt.astimezone(parse_iso("2000-01-01T00:00:00Z").tzinfo).isoformat().replace("+00:00", "Z")


def _rng(handle: str) -> Random:
    return Random(crc32(handle.encode("utf-8")))


def _gen_videos(rng, author_id, median_views, er, n, newest, cadence_pw, boost_mult=None, boost_recent=0):
    spacing = 7.0 / max(cadence_pw, 0.5)
    times = list(reversed([newest - timedelta(days=spacing * i) for i in range(n)]))
    factors = [rng.uniform(0.7, 1.5) for _ in range(n)]
    # Normalize by the median of the NON-spike posts so the reported "typical views"
    # (median excluding self-outliers) lands on the descriptor's median_views.
    normal = factors[: n - boost_recent] if boost_recent else factors
    med = median(normal) or 1.0
    plays = [max(50, int(median_views * f / med)) for f in factors]
    if boost_mult and boost_recent:
        for j in range(1, boost_recent + 1):
            plays[-j] = int(median_views * boost_mult)  # self-outlier spike (most recent)
    # Engagement jitter is median-normalized (same rule as plays above) so the
    # REALIZED per-video engagement-ratio median lands on the descriptor's ER —
    # every ER a rationale or why-copy quotes is the number the pipeline computes.
    emults = [rng.uniform(0.9, 1.1) for _ in range(n)]
    emed = median(emults) or 1.0
    vids = []
    for i, (t, pv) in enumerate(zip(times, plays)):
        eng = round(pv * er / 100.0 * emults[i] / emed)  # = digg+comment+share exactly
        comment = round(eng * 0.07)
        share = round(eng * 0.03)
        vids.append(RawVideo(
            video_id=f"{author_id}_v{i}", play_count=pv,
            digg_count=max(eng - comment - share, 0), comment_count=comment,
            share_count=share, collect_count=round(eng * 0.02),
            create_time_iso=_iso(t), text=f"clip {i}", hashtags=["skincare", "beauty"],
        ))
    return vids


def _clean_text(rng) -> str:
    return f"{rng.choice(_CLEAN_A)}{rng.choice(_CLEAN_B)}"


def _gen_clean_comments(rng, author_id, video_url, n, newest):
    out = []
    for i in range(n):
        t = newest - timedelta(hours=rng.uniform(0, 20 * 24))
        uid = f"{author_id}_u{i}"
        out.append(RawComment(
            cid=f"{author_id}_c{i}", uid=uid, unique_id=f"@{uid}", text=_clean_text(rng),
            digg_count=rng.randint(0, 25), reply_comment_total=rng.randint(0, 4),
            create_time_iso=_iso(t), video_web_url=video_url,
        ))
    return out


def _gen_pod_comments(rng, author_id, video_url, newest, organic=100):
    """Pod signature: shared accounts, a tight burst, templated dead-end comments,
    spread across ~14 days; plus organic comments to dilute (share still >=15%)."""
    out = []
    # 1) burst: 30 pod comments within ~110s on the newest video
    for i in range(30):
        uid = POD_POOL[i % len(POD_POOL)]
        t = newest + timedelta(seconds=rng.uniform(0, 110))
        out.append(RawComment(
            cid=f"{author_id}_pb{i}", uid=uid, unique_id=f"@{uid}",
            text=rng.choice(_POD_TEXTS), digg_count=0, reply_comment_total=0,
            create_time_iso=_iso(t), video_web_url=video_url,
        ))
    # 2) scattered pod comments over the prior 14 days (drives span + reuse share)
    for i in range(len(POD_POOL) * 2):
        uid = POD_POOL[i % len(POD_POOL)]
        t = newest - timedelta(days=rng.uniform(0.2, 14))
        out.append(RawComment(
            cid=f"{author_id}_ps{i}", uid=uid, unique_id=f"@{uid}",
            text=rng.choice(_POD_TEXTS), digg_count=0, reply_comment_total=0,
            create_time_iso=_iso(t), video_web_url=video_url,
        ))
    # 3) organic filler (varied, healthy)
    for i in range(organic):
        uid = f"{author_id}_org{i}"
        t = newest - timedelta(hours=rng.uniform(0, 14 * 24))
        out.append(RawComment(
            cid=f"{author_id}_co{i}", uid=uid, unique_id=f"@{uid}", text=_clean_text(rng),
            digg_count=rng.randint(0, 30), reply_comment_total=rng.randint(0, 5),
            create_time_iso=_iso(t), video_web_url=video_url,
        ))
    return out


def _gen_bought_comments(rng, author_id, video_url, newest, n=140, thin_share=0.68):
    """Bought base: mostly empty/non-Thai accounts, sampled by the 2nd-pass enricher."""
    out = []
    for i in range(n):
        uid = f"{author_id}_bot{i}"
        t = newest - timedelta(hours=rng.uniform(0, 30 * 24))
        thin = i < int(n * thin_share)
        # varied text (index-tagged): bought followers is a distinct signal from a
        # comment pod — the audience is empty accounts, not templated spam.
        out.append(RawComment(
            cid=f"{author_id}_bc{i}", uid=uid, unique_id=f"@{uid}",
            text=f"{rng.choice(_BOT_TEXTS)} {i}", digg_count=rng.randint(0, 2), reply_comment_total=0,
            create_time_iso=_iso(t), video_web_url=video_url,
            commenter_post_count=(rng.randint(0, 3) if thin else rng.randint(20, 200)),
            commenter_has_thai_history=(False if thin else True),
        ))
    return out


class SeedDatasetSource(KOLSource):
    name = "seed"

    def __init__(self, spec_path: str | Path | None = None):
        spec = json.loads(Path(spec_path or _FIXTURE).read_text(encoding="utf-8"))
        self._client = spec["client"]
        as_of = parse_iso(spec["as_of"])
        self.as_of = as_of  # dataset reference date; pipeline uses it as "now"
        self._candidates: list[RawKOL] = []
        self._pres: dict[str, Presentation] = {}
        self._corpus_extra: list[RawKOL] = []

        for d in spec["kols"]:
            kol, pres = self._expand(d, as_of)
            self._candidates.append(kol)
            self._pres[d["id"]] = pres

        self._build_fillers(spec.get("cohort_fillers", {}), as_of)
        self._build_decoys(spec.get("pod_decoys", 0), as_of)
        self._build_overlap(spec.get("audience_overlap"), as_of)

    # ── expansion ──────────────────────────────────────────────────────────
    def _expand(self, d: dict, as_of) -> tuple[RawKOL, Presentation]:
        rng = _rng(d["handle"])
        author_id = d["id"]
        newest = as_of - timedelta(days=d["last_posted_days_ago"])
        arch = d["archetype"]
        boost_mult = d.get("boost_mult")
        boost_recent = 3 if arch == "comment_pod" else (2 if arch == "boosted" else 0)
        cadence = {"micro": 3.5, "mid": 2.5, "macro": 5.0}.get(d["tier"], 3.0)

        videos = _gen_videos(
            rng, author_id, d["median_views"], d["engagement_rate"], 20, newest, cadence,
            boost_mult=boost_mult, boost_recent=boost_recent,
        )
        vurl = f"https://www.tiktok.com/{d['handle']}/video/latest"
        if arch == "comment_pod":
            comments = _gen_pod_comments(rng, author_id, vurl, newest)
        elif arch == "bought_followers":
            comments = _gen_bought_comments(rng, author_id, vurl, newest)
        else:
            comments = _gen_clean_comments(rng, author_id, vurl, 100, newest)

        profile = RawProfile(
            author_id=author_id, unique_id=d["handle"], nickname=d["name"],
            fans=d["followers"], following=rng.randint(50, 800),
            video_count=200 + rng.randint(0, 300), verified=(d["tier"] in ("macro",)),
            signature=d["category"], region=d["region"],
        )
        # Optional brand-safety probe: a real taboo phrase in one caption so the
        # (separate-axis) brand-safety scanner has something to catch on the demo cohort.
        probe = d.get("brand_safety_probe")
        if probe and videos:
            videos[0] = videos[0].model_copy(update={"text": f"{videos[0].text} {probe}"})
        kol = RawKOL(profile=profile, videos=videos, comments=comments,
                     vertical=d["vertical"], tier=d["tier"])
        pres = Presentation(
            id=d["id"], name=d["name"], category=d["category"], category_th=d["category_th"],
            avatar_initials=d["initials"], avatar_hue=d["hue"],
            topic_score=d["topic_score"], audience_score=d["audience_score"],
            brand_safety_status=d["brand_safety"]["status"], brand_safety_note=d["brand_safety"].get("note"),
            conflict_status=d["conflict"]["status"], conflict_note=d["conflict"].get("note"),
            hitl=d["hitl"],
            topic_rationale=d.get("topic_rationale"),
            audience_rationale=d.get("audience_rationale"),
            why_en=d.get("why_en"),
            why_th=d.get("why_th"),
        )
        return kol, pres

    def _build_fillers(self, fillers: dict, as_of):
        bands = {
            "beauty:micro": (4.5, 8.5, 20000, 90000),
            "beauty:mid": (3.8, 6.0, 100000, 260000),
        }
        for cell, count in fillers.items():
            if cell not in bands:
                continue
            vertical, tier = cell.split(":")
            er_lo, er_hi, f_lo, f_hi = bands[cell]
            for i in range(int(count)):
                handle = f"@filler_{vertical}_{tier}_{i}"
                rng = _rng(handle)
                aid = f"fill_{tier}_{i}"
                followers = rng.randint(f_lo, f_hi)
                mv = int(followers * rng.uniform(0.9, 1.4))  # healthy view-to-follower
                er = round(rng.uniform(er_lo, er_hi), 1)
                newest = as_of - timedelta(days=rng.randint(1, 5))
                videos = _gen_videos(rng, aid, mv, er, 20, newest, 3.0)
                comments = _gen_clean_comments(rng, aid, f"https://www.tiktok.com/{handle}/v", 60, newest)
                profile = RawProfile(author_id=aid, unique_id=handle, nickname=handle,
                                     fans=followers, signature="beauty", region="Bangkok")
                self._corpus_extra.append(RawKOL(profile=profile, videos=videos,
                                                 comments=comments, vertical=vertical, tier=tier))

    def _build_decoys(self, n: int, as_of):
        """Unrelated creators the same pod also spams — makes each pod account appear
        across REUSE_MIN_CREATORS+ creators so cross-creator reuse validly fires."""
        for i in range(int(n)):
            handle = f"@decoy_{i}"
            rng = _rng(handle)
            aid = f"decoy_{i}"
            newest = as_of - timedelta(days=rng.randint(1, 6))
            videos = _gen_videos(rng, aid, rng.randint(30000, 120000), round(rng.uniform(4, 7), 1),
                                 12, newest, 3.0)
            vurl = f"https://www.tiktok.com/{handle}/v"
            comments = []
            for j, uid in enumerate(POD_POOL):
                for k in range(2):
                    t = newest - timedelta(days=rng.uniform(0.2, 14))
                    comments.append(RawComment(
                        cid=f"{aid}_p{j}_{k}", uid=uid, unique_id=f"@{uid}",
                        text=rng.choice(_POD_TEXTS), digg_count=0, reply_comment_total=0,
                        create_time_iso=_iso(t), video_web_url=vurl,
                    ))
            profile = RawProfile(author_id=aid, unique_id=handle, nickname=handle,
                                 fans=rng.randint(40000, 200000), signature="misc", region="Unknown")
            # decoys sit in their own cohort cell so they never pollute beauty stats
            self._corpus_extra.append(RawKOL(profile=profile, videos=videos, comments=comments,
                                             vertical="_decoy", tier="_decoy"))

    def _build_overlap(self, cfg: dict | None, as_of):
        """Inject a pool of SHARED commenters into exactly the two named clean creators so
        the commenter-overlap dedup has something real to catch. The pool spans only two
        creators (< REUSE_MIN_CREATORS=3), so it never trips a false pod flag — both stay
        risk-clear; it only shows up as audience overlap."""
        if not cfg:
            return
        ids = cfg.get("creators", [])
        n = int(cfg.get("shared", 0))
        if len(ids) < 2 or n <= 0:
            return
        pool = [f"aud_{i:03d}" for i in range(n)]
        targets = [k for k in self._candidates if k.profile.author_id in ids]
        for kol in targets:
            rng = _rng(f"overlap_{kol.profile.author_id}")
            vurl = f"https://www.tiktok.com/{kol.profile.unique_id}/video/latest"
            for j, uid in enumerate(pool):
                t = as_of - timedelta(hours=rng.uniform(0, 20 * 24))
                kol.comments.append(RawComment(
                    cid=f"{kol.profile.author_id}_aud{j}", uid=uid, unique_id=f"@{uid}",
                    text=_clean_text(rng), digg_count=rng.randint(0, 20), reply_comment_total=0,
                    create_time_iso=_iso(t), video_web_url=vurl,
                ))

    # ── interface ──────────────────────────────────────────────────────────
    def client_brief(self) -> ClientBrief:
        return ClientBrief.model_validate(self._client)

    def fetch_candidates(self, brief: ClientBrief | None = None) -> list[RawKOL]:
        return self._candidates

    def reuse_corpus(self) -> list[RawKOL]:
        return self._corpus_extra

    def presentation(self, kol: RawKOL) -> Presentation:
        return self._pres[kol.profile.author_id]
