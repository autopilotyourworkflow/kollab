"""Async sourcing runs: a scrape can take minutes, far longer than an HTTP request
should be held open, so POST /api/runs starts the work in a background thread and
persists its state + result in the database. The frontend polls GET /api/runs/{id}.

State lives in Postgres (Neon) so a poll from any request — even after the free
instance sleeps and wakes — sees the same run. The runner never raises out: any
failure is recorded on the row as status=error, so a poll always gets an answer."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterable

from app.db import get_sessionmaker
from app.models import Run

# Run ids the user has asked to stop. In-process (single Render instance); the
# running job thread polls it via cancel_check, and request_cancel adds to it.
_cancel_requested: set[str] = set()


def _session():
    factory = get_sessionmaker()
    if factory is None:
        raise RuntimeError("No database configured — set DATABASE_URL to enable async runs.")
    return factory()


def create_run(run_id: str, brand: str, preset: str, brief: dict | None) -> None:
    with _session() as s:
        s.add(Run(id=run_id, brand=brand, preset=preset, brief=brief, status="queued"))
        s.commit()


def get_run(run_id: str) -> dict | None:
    with _session() as s:
        row = s.get(Run, run_id)
        return row.to_dict() if row else None


def _update(run_id: str, **fields) -> None:
    with _session() as s:
        row = s.get(Run, run_id)
        if row is None:
            return
        for key, value in fields.items():
            setattr(row, key, value)
        s.commit()


def run_job(run_id: str, brief_dict: dict | None, preset: str, expand: bool,
            exclude: list[str], apify_token: str | None, anthropic_key: str | None) -> None:
    """Execute one run to completion, recording the outcome on its row. Runs in a
    background thread, so it re-installs the per-request keys (contextvars don't cross
    threads) and swallows every error into status=error."""
    from app.config import reset_request_credentials, set_request_credentials
    from app.schemas import ClientBrief
    from app.service import BadRequest, LiveRunError, run_shortlist
    from app.sources.apify import RunCancelled

    token = set_request_credentials(apify_token, anthropic_key)
    try:
        _update(run_id, status="running")
        brief = ClientBrief.model_validate(brief_dict) if brief_dict else None
        response = run_shortlist(brief, preset=preset, expand=expand, exclude=exclude,
                                 cancel_check=lambda: run_id in _cancel_requested)
        if run_id in _cancel_requested:  # stop that raced past the last checkpoint
            _update(run_id, status="cancelled")
        else:
            _update(run_id, status="done", result=response.model_dump(by_alias=True))
    except RunCancelled:
        _update(run_id, status="cancelled")
    except (LiveRunError, BadRequest) as e:
        _update(run_id, status="error", error=str(e))
    except Exception as e:  # never leave a run wedged in "running"
        _update(run_id, status="error", error=f"{type(e).__name__}: {e}")
    finally:
        reset_request_credentials(token)
        _cancel_requested.discard(run_id)


def request_cancel(run_id: str, apify_token: str | None = None,
                   apify_tokens: list[str] | None = None) -> dict | None:
    """Stop a run: flag it (the loop's cancel_check trips at the next phase boundary),
    mark it cancelled, and best-effort abort its in-flight Apify actor so the slow
    search stops billing at once. Returns the updated run, or None if unknown.

    `apify_tokens` lets the caller pass EVERY candidate key (e.g. the whole env pool) so
    the abort still fires in the recommended pool-only deployment, where no single legacy
    `apify_token` is set but the run leased one of the numbered pool keys. Each pool key is
    a separate Apify account, so we issue the abort on each — abort only affects RUNNING
    actor-runs on that account, so this is safe and best-effort."""
    run = get_run(run_id)
    if run is None:
        return None
    if run["status"] in ("done", "error", "cancelled"):
        return run  # already terminal — nothing to stop
    _cancel_requested.add(run_id)
    _update(run_id, status="cancelled")
    # De-duplicate the candidate tokens, preserving order (request key first).
    candidates: list[str] = []
    for tok in ([apify_token] if apify_token else []) + list(apify_tokens or []):
        if tok and tok not in candidates:
            candidates.append(tok)
    for tok in candidates:
        _abort_running_apify(tok)
    return get_run(run_id)


def _abort_running_apify(token: str) -> None:
    """Abort the account's currently-running actor runs so a stopped job stops
    spending immediately. Crude (single free-tier instance runs one job at a time),
    best-effort, and never raises."""
    try:
        import httpx

        listing = httpx.get("https://api.apify.com/v2/actor-runs",
                            params={"token": token, "status": "RUNNING"}, timeout=15)
        for run in listing.json().get("data", {}).get("items", []):
            rid = run.get("id")
            if rid:
                httpx.post(f"https://api.apify.com/v2/actor-runs/{rid}/abort",
                           params={"token": token}, timeout=15)
    except Exception:
        pass


def start_run(brief_dict: dict | None, preset: str, expand: bool, exclude: Iterable[str],
              apify_token: str | None, anthropic_key: str | None) -> str:
    """Create the run row and kick off its background thread; return the run id
    immediately. The keys are captured here (inside the request's credential scope)
    and handed to the thread, which re-installs them."""
    run_id = uuid.uuid4().hex
    brand = str((brief_dict or {}).get("brand") or "")
    create_run(run_id, brand=brand, preset=preset, brief=brief_dict)
    thread = threading.Thread(
        target=run_job,
        args=(run_id, brief_dict, preset, expand, list(exclude), apify_token, anthropic_key),
        daemon=True,
    )
    thread.start()
    return run_id
