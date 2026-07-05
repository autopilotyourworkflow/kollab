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

    token = set_request_credentials(apify_token, anthropic_key)
    try:
        _update(run_id, status="running")
        brief = ClientBrief.model_validate(brief_dict) if brief_dict else None
        response = run_shortlist(brief, preset=preset, expand=expand, exclude=exclude)
        _update(run_id, status="done", result=response.model_dump(by_alias=True))
    except (LiveRunError, BadRequest) as e:
        _update(run_id, status="error", error=str(e))
    except Exception as e:  # never leave a run wedged in "running"
        _update(run_id, status="error", error=f"{type(e).__name__}: {e}")
    finally:
        reset_request_credentials(token)


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
