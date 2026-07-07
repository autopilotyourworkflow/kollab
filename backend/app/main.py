"""FastAPI app — the judgment layer as an API.

The deployed frontend can point at this to replace its bundled fixtures with a live
call; both render the identical ShortlistResponse contract. Runs credential-free on
SeedDatasetSource. CORS is open to the Pages demo + localhost dev.

Live sourcing is slow (minutes), so it runs asynchronously: POST /api/runs starts a
background job whose state lives in the database, and the frontend polls
GET /api/runs/{id}. POST /api/shortlist keeps the synchronous path for fixtures and
direct/API use.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager, contextmanager

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app import keypool
from app.auth import (
    _DUMMY_HASH,
    auth_available,
    issue_token,
    normalize_email,
    verify_password,
    verify_token,
)
from app.fraud.graph import get_graph_store
from app.config import (
    get_settings,
    request_override_present,
    reset_request_credentials,
    set_request_credentials,
)
from app.credit import fetch_apify_credit
from app.db import database_url, db_status, init_db
from app.ingest import extract_brand_dna
from app.schemas import (
    BrandDnaRequest,
    BrandDnaResponse,
    ClientBrief,
    DeliveredPostRequest,
    DeliveryAudit,
    DeliveryLogRequest,
    LoginRequest,
    OutreachDraft,
    OutreachRequest,
    ShortlistResponse,
    SignupRequest,
)
from app.service import BadRequest, LiveRunError, run_shortlist
from app.sources.plans import public_payload


@contextmanager
def _request_keys(x_apify_token: str | None, x_anthropic_key: str | None):
    """Bring-your-own-key: a visitor who pasted their own Apify/Claude key in
    Settings sends it per-request as a header. We install it for the body of THIS
    request only (contextvar) and always reset it — the key is never persisted,
    never logged, never returned. Absent header -> the operator's shared key (if
    sharing is on). Set/read/reset all run in the endpoint's own thread, so the deep
    callers (Apify loop, LLM callers, credit check) transparently see the right key
    with no cross-request leakage."""
    token = set_request_credentials(x_apify_token, x_anthropic_key)
    try:
        yield
    finally:
        reset_request_credentials(token)


def _serve(run):
    """Map the service's typed errors to HTTP codes (400 bad input, 503 live-path
    precondition) so every endpoint answers honestly, never an opaque 500."""
    try:
        return run()
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LiveRunError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


def _refresh_minutes() -> int:
    raw = os.getenv("KOLLAB_KEY_REFRESH_MINUTES", "20")
    try:
        return max(1, int(raw))
    except ValueError:
        return 20


def _start_key_refresher() -> None:
    """Proactive rotation: a daemon thread that re-polls each pool key's Apify balance
    every KOLLAB_KEY_REFRESH_MINUTES (default 20), flipping keys active->low->exhausted
    BEFORE a run reaches the wall. The reactive swap in ApifyAdapter is the safety net
    between polls. No-op when the pool is disabled; never raises; never blocks startup.
    (This in-process loop runs on Render's free tier — no paid cron service needed. It
    also runs one refresh immediately on boot, which covers a free instance waking up.)"""
    import threading

    try:
        from app import keypool

        if not keypool.available():
            return
    except Exception:
        return

    interval = max(60, _refresh_minutes() * 60)

    def _loop() -> None:
        import time

        while True:
            try:
                from app import keypool

                keypool.refresh_all()
            except Exception:
                pass
            time.sleep(interval)

    threading.Thread(target=_loop, name="apify-key-refresher", daemon=True).start()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create the runs + apify_keys tables when a database is configured (idempotent). A
    # bad/absent DATABASE_URL must never stop the seed demo from serving, so this is
    # best-effort. Then start the background pool-balance refresher (no-op if disabled).
    try:
        init_db()
    except Exception:
        pass
    try:
        _start_key_refresher()
    except Exception:
        pass
    # Best-effort cleanup of idle guest accounts (no cron needed — free-tier cold starts
    # run this often). Never blocks startup.
    try:
        from app.accounts import reap_guests

        reap_guests()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Kollab API",
    version=__version__,
    description="Brand-fit + fraud-vetting judgment layer for Thai TikTok KOLs.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://kollab.autopilotyourworkflow.com",  # production custom domain
        "https://kollab-64c.pages.dev",               # Pages project domain
        "http://localhost:5178",
        "http://localhost:5173",
    ],
    # Cloudflare Pages preview deploys get a per-commit subdomain
    # (<hash>.kollab-64c.pages.dev) — allow those too so preview links run live.
    allow_origin_regex=r"https://[a-z0-9-]+\.kollab-64c\.pages\.dev",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "source": s.source,
        "apify_enabled": s.apify_enabled,
        "llm_enabled": s.llm_enabled,
        "llm_rerank": s.llm_rerank and s.llm_enabled,
        "min_cohort_n": s.min_cohort_n,
        "run_budget_usd": s.run_budget_usd,
        # Whether the operator shares their own keys as the fallback (kill switch).
        "shared_key": s.shared_key,
        # Cheap flag (no DB round-trip); /api/db-status does the live check.
        "db_configured": bool(database_url()),
        # Env-configured Apify key pool (APIFY_TOKEN, APIFY_TOKEN_1..N): count + how
        # many are currently healthy. No network, no tokens — just a sanity readout.
        "apify_key_pool": keypool.status(),
        # Which backend the persistent commenter graph runs on (cheap flag; the full
        # size/pod readout is GET /api/graph). "neon" = durable, "memory" = demo.
        "commenter_graph": get_graph_store().backend,
        # Whether accounts / the durable workspace are available (a signing secret exists).
        "auth": auth_available(),
    }


@app.get("/api/graph")
def graph_endpoint() -> dict:
    """The persistent cross-run commenter graph readout — the fraud-recall moat, made
    inspectable: how many creators/commenters/edges it holds and how many pod clusters
    it has learned. `durable` is true on the Neon backend, false for the ephemeral demo
    graph. Aggregate counts only — never a uid or handle. Never raises."""
    return get_graph_store().stats()


@app.get("/api/db-status")
def db_status_endpoint() -> dict:
    """Live database connectivity — runs a real SELECT 1. A green result confirms the
    DATABASE_URL (Neon) credentials, network, and SSL all work from this host. Never
    leaks the URL/password."""
    return db_status()


@app.get("/api/credit")
def credit(
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> dict:
    """Live credit for the key THIS request runs on — the meter behind the run-time
    low-credit warning. `apify.source` is 'user' (visitor pasted their own key),
    'shared' (operator's key), or 'none'. Anthropic has no public balance endpoint,
    so we report presence only. Never returns any key value."""
    with _request_keys(x_apify_token, x_anthropic_key):
        s = get_settings()

        def _source(override_key: str, owner_present: bool) -> str:
            if request_override_present(override_key):
                return "user"
            return "shared" if (s.shared_key and owner_present) else "none"

        # The token the meter reports on: the visitor's own key / legacy env key if set,
        # otherwise (sharing on) a healthy key from the env pool — so the meter stays
        # honest when the operator only set the numbered APIFY_TOKEN_1..N.
        meter_token = s.effective_apify_token
        if meter_token is None and s.shared_key and not request_override_present("apify_token"):
            lease = keypool.acquire()
            meter_token = lease.token if lease else None

        apify = fetch_apify_credit(meter_token)
        apify["source"] = _source("apify_token", s.apify_enabled or keypool.available())
        apify["hasKey"] = bool(meter_token)

        return {
            "sharedKey": s.shared_key,
            "apify": apify,
            "anthropic": {
                "hasKey": bool(s.effective_anthropic_api_key),
                "source": _source("anthropic_api_key", bool(s.anthropic_api_key)),
                "note": "Anthropic has no public balance API — usage is on console.anthropic.com.",
            },
        }


@app.get("/api/shortlist", response_model=ShortlistResponse)
def get_shortlist() -> ShortlistResponse:
    """The default demo shortlist (Glow Lab) on curated fixtures."""
    return _serve(lambda: run_shortlist(None))


@app.post("/api/shortlist", response_model=ShortlistResponse)
def post_shortlist(
    brief: ClientBrief,
    preset: str | None = None,
    creators: int | None = None,
    comments: int | None = None,
    cap_usd: float | None = None,
    expand: bool = False,
    exclude: list[str] = Query(default=[]),
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> ShortlistResponse:
    """Synchronously run the pipeline for a brief. Fixtures mode returns the curated
    cohort; a live source blocks on the scrape (use POST /api/runs for the non-blocking
    path). `?preset=scan|standard|deep`, optional creators/comments overrides, cap_usd
    never exceeding the server ceiling. A visitor's own key rides the
    X-Apify-Token / X-Anthropic-Key headers. `?expand=1` skips creators this brand
    already holds; `?exclude=@handle` adds explicit skips; `excludedKnown` reports the
    dedup count."""
    with _request_keys(x_apify_token, x_anthropic_key):
        return _serve(lambda: run_shortlist(
            brief, preset=preset, creators=creators, comments=comments,
            cap_usd=cap_usd, expand=expand, exclude=exclude,
        ))


@app.post("/api/runs")
def start_run_endpoint(
    brief: ClientBrief,
    preset: str = "standard",
    expand: bool = False,
    exclude: list[str] = Query(default=[]),
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> dict:
    """Start an async sourcing run; return its id immediately (a real scrape takes
    minutes — too long to hold the request open). Poll GET /api/runs/{id} for the
    result. Requires a database (run state lives there); without one, use
    POST /api/shortlist. The visitor's own key (if supplied) is captured here and used
    for the whole run."""
    if not database_url():
        raise HTTPException(
            status_code=503,
            detail="Async runs need a database — set DATABASE_URL (Neon). "
                   "Without it, POST /api/shortlist runs synchronously.",
        )
    with _request_keys(x_apify_token, x_anthropic_key):
        s = get_settings()
        apify = s.effective_apify_token
        anthropic = s.effective_anthropic_api_key
    from app.runs import start_run

    run_id = start_run(brief.model_dump(by_alias=True), preset, expand, exclude, apify, anthropic)
    return {"id": run_id, "status": "queued"}


@app.get("/api/runs/{run_id}")
def get_run_endpoint(run_id: str) -> dict:
    """Poll a run: {status: queued|running|done|error|cancelled, result?, error?}.
    `result` is the camelCase ShortlistResponse the frontend merges once status is
    done. State lives in the DB, so a poll works after a refresh or a new session."""
    from app.runs import get_run

    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.post("/api/runs/{run_id}/cancel")
def cancel_run_endpoint(
    run_id: str,
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> dict:
    """Stop a running job and abort its in-flight Apify actor so it stops spending.
    Idempotent: cancelling a finished run just returns it."""
    with _request_keys(x_apify_token, x_anthropic_key):
        token = get_settings().effective_apify_token
    from app.runs import request_cancel

    run = request_cancel(run_id, apify_token=token)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/api/run-plans")
def run_plans() -> dict:
    """Run-depth presets with computed cost estimates, default caps, and honest
    quality notes — what each spend buys in evidence terms."""
    return public_payload()


@app.post("/api/brand-dna", response_model=BrandDnaResponse)
def brand_dna(
    req: BrandDnaRequest,
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> BrandDnaResponse:
    """Website → structured brief. Claude → Gemini → rules skeleton; the response
    names its source and flags degraded extraction — the UI badges it honestly. A
    visitor's own Claude key (X-Anthropic-Key header, from Settings) runs the
    extraction on their credit; without any key it returns the labeled skeleton."""
    with _request_keys(x_apify_token, x_anthropic_key):
        result = extract_brand_dna(req.website)
        return BrandDnaResponse(
            brief=result.brief, degraded=result.degraded, source=result.source, note=result.note
        )


@app.post("/api/re-audit", response_model=DeliveryAudit)
def reaudit_endpoint(req: DeliveredPostRequest) -> DeliveryAudit:
    """Re-audit a booked creator's actual DELIVERED post through the same structural
    detectors and diff it against the pre-booking authenticity. Live delivered-post data
    on the request is used when present; the demo loads a fixture for a seed handle. 404
    only when neither is available."""
    from app.fraud.reaudit import (
        build_kol_from_request,
        load_delivered_fixture,
        reaudit_delivered_post,
    )

    kol = build_kol_from_request(req) or load_delivered_fixture(req.handle)
    if kol is None:
        raise HTTPException(
            status_code=404,
            detail=f"No delivered-post data for {req.handle}. Pass the scraped post, or "
                   f"re-audit one of the demo creators (e.g. @ploy.skinnote).",
        )
    return reaudit_delivered_post(kol, pre_authenticity=req.pre_authenticity,
                                  graph_store=get_graph_store())


@app.post("/api/deliveries")
def log_delivery_endpoint(req: DeliveryLogRequest) -> dict:
    """Log a campaign outcome (projected vs actual views) and return the row + the updated
    reliability for that creator. Needs a database (503 without one, like /api/runs)."""
    if not database_url():
        raise HTTPException(
            status_code=503,
            detail="The delivery ledger needs a database — set DATABASE_URL (Neon).",
        )
    from app.ledger import record_delivery, reliability

    row = record_delivery(req.brand, req.handle, req.projected_views, req.actual_views, req.note)
    return {"delivery": row, "reliability": reliability(req.handle)}


@app.get("/api/deliveries")
def list_deliveries_endpoint(handle: str = Query(...)) -> dict:
    """List a creator's logged deliveries + their reliability. Empty (learning state) until
    the first delivery is logged. Needs a database (503 without one)."""
    if not database_url():
        raise HTTPException(
            status_code=503,
            detail="The delivery ledger needs a database — set DATABASE_URL (Neon).",
        )
    from app.ledger import deliveries_for, reliability

    return {"handle": handle, "deliveries": deliveries_for(handle), "reliability": reliability(handle)}


@app.post("/api/outreach", response_model=OutreachDraft)
def outreach_endpoint(
    req: OutreachRequest,
    x_apify_token: str | None = Header(default=None),
    x_anthropic_key: str | None = Header(default=None),
) -> OutreachDraft:
    """Draft a first-contact message to a creator, grounded ONLY in safe (non-fraud,
    non-rate) data points and citation-validated. A visitor's own Claude key runs it on
    their credit; without any key it returns a labelled deterministic template. Never 503."""
    with _request_keys(x_apify_token, x_anthropic_key):
        from app.matching.outreach import generate_outreach

        return generate_outreach(req.kol, req.brief)


# ── Accounts + durable workspace ─────────────────────────────────────────────
# A tiny in-process sliding-window rate limiter for the UNAUTHENTICATED auth endpoints
# (bounds guest-mint / signup-scrypt / login-guess floods without a new dependency). Keyed
# by client IP; buckets self-trim. Single Render instance, so process-local is sufficient.
import time as _time
from collections import defaultdict, deque

_rl_buckets: dict[str, deque] = defaultdict(deque)


def _rate_limit(request: Request | None, action: str, limit: int, window_s: int) -> None:
    ip = (request.client.host if request and request.client else "anon")
    now = _time.time()
    dq = _rl_buckets[f"{action}:{ip}"]
    while dq and dq[0] < now - window_s:
        dq.popleft()
    if len(dq) >= limit:
        raise HTTPException(status_code=429, detail="Too many attempts — please wait a moment and try again.")
    dq.append(now)


def _require_auth() -> None:
    if not auth_available():
        raise HTTPException(status_code=503,
                            detail="Accounts need a database — set DATABASE_URL (Neon).")


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """Resolve the bearer token to a user, or 401. 503 (never 500) with no database."""
    _require_auth()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    uid = verify_token(authorization[7:].strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    from app.accounts import get_user

    user = get_user(uid)
    if user is None:  # e.g. a reaped guest
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def _valid_email(email: str) -> bool:
    e = normalize_email(email)
    return "@" in e and "." in e.split("@")[-1] and len(e) <= 254


@app.post("/api/auth/signup")
def signup(req: SignupRequest, request: Request) -> dict:
    _require_auth()
    _rate_limit(request, "signup", limit=10, window_s=3600)
    if not _valid_email(req.email):
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    from sqlalchemy.exc import IntegrityError

    from app.accounts import create_user, find_by_email

    # Cheap existence check first, so a duplicate email 409s WITHOUT spending scrypt.
    if find_by_email(req.email):
        raise HTTPException(status_code=409, detail="That email is already registered.")
    try:
        user = create_user(req.email, req.password)
    except IntegrityError:
        # a race between the check and the insert — still just a duplicate
        raise HTTPException(status_code=409, detail="That email is already registered.")
    # any other exception (DB down, etc.) propagates -> honest 500/503, never a fake 409
    return {"token": issue_token(user["id"]), "user": user}


@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request) -> dict:
    _require_auth()
    _rate_limit(request, "login", limit=30, window_s=300)
    from app.accounts import find_by_email, get_user

    row = find_by_email(req.email)
    # Spend the same scrypt cost whether or not the email exists (no enumeration timing gap),
    # and answer with an identical message either way.
    if row is None:
        verify_password(req.password, _DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return {"token": issue_token(row["id"]), "user": get_user(row["id"])}


@app.post("/api/auth/guest")
def guest(request: Request) -> dict:
    """One-click 'Explore the demo': mint an isolated guest account seeded with the demo
    Glow Lab shortlist, and return a token."""
    _require_auth()
    _rate_limit(request, "guest", limit=15, window_s=3600)
    from app.accounts import create_guest, seed_guest_workspace

    user = create_guest()
    try:
        seed_guest_workspace(user["id"])
    except Exception:
        pass  # a seeding hiccup shouldn't block sign-in; the workspace just starts empty
    return {"token": issue_token(user["id"]), "user": user}


@app.get("/api/auth/me")
def whoami(user: dict = Depends(current_user)) -> dict:
    return user


@app.post("/api/auth/logout")
def logout() -> dict:
    # Tokens are stateless; the client drops it. (Endpoint exists for a clean client API.)
    return {"ok": True}


@app.get("/api/shortlists")
def list_shortlists_endpoint(user: dict = Depends(current_user)) -> dict:
    from app.accounts import list_shortlists

    return {"shortlists": list_shortlists(user["id"])}


@app.post("/api/shortlists", status_code=201)
def create_shortlist_endpoint(payload: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    kols = payload.get("kols")
    if not isinstance(kols, list) or not all(isinstance(k, dict) for k in kols):
        raise HTTPException(status_code=400, detail="A shortlist needs a kols array of objects.")
    from app.accounts import create_shortlist

    return {"shortlist": create_shortlist(user["id"], payload)}


@app.get("/api/shortlists/{sid}")
def get_shortlist_endpoint(sid: str, user: dict = Depends(current_user)) -> dict:
    from app.accounts import get_shortlist

    entry = get_shortlist(user["id"], sid)
    if entry is None:
        raise HTTPException(status_code=404, detail="Shortlist not found")
    return {"shortlist": entry}


@app.post("/api/shortlists/{sid}/kols")
def append_kols_endpoint(sid: str, body: dict = Body(...), user: dict = Depends(current_user)) -> dict:
    kols = body.get("kols") or []
    if not isinstance(kols, list) or not all(isinstance(k, dict) for k in kols):
        raise HTTPException(status_code=400, detail="kols must be an array of objects.")
    from app.accounts import append_kols

    res = append_kols(user["id"], sid, kols)
    if res is None:
        raise HTTPException(status_code=404, detail="Shortlist not found")
    return {"added": res["added"], "shortlist": res["entry"]}


@app.put("/api/shortlists/{sid}/decisions/{kol_id}", status_code=204)
def set_decision_endpoint(sid: str, kol_id: str, body: dict = Body(...),
                          user: dict = Depends(current_user)) -> None:
    from app.accounts import set_decision

    if not set_decision(user["id"], sid, kol_id, body):
        raise HTTPException(status_code=404, detail="Shortlist not found")


@app.post("/api/shortlists/{sid}/source-live")
def source_live_endpoint(sid: str, user: dict = Depends(current_user)) -> dict:
    from app.accounts import mark_source_live

    entry = mark_source_live(user["id"], sid)
    if entry is None:
        raise HTTPException(status_code=404, detail="Shortlist not found")
    return {"shortlist": entry}


@app.delete("/api/shortlists/{sid}", status_code=204)
def delete_shortlist_endpoint(sid: str, user: dict = Depends(current_user)) -> None:
    from app.accounts import delete_shortlist

    if not delete_shortlist(user["id"], sid):
        raise HTTPException(status_code=404, detail="Shortlist not found")


@app.get("/")
def root() -> dict:
    return {
        "name": "Kollab API",
        "tagline": "Not a scraper, not a database — the brand-fit and vetting brain.",
        "docs": "/docs",
        "endpoints": ["/health", "/api/shortlist", "/api/runs"],
    }
