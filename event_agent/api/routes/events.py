"""Events API routes."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from event_agent.agents.crew import AgentCrew
from event_agent.config.settings import get_settings
from event_agent.db.engine import get_session
from event_agent.db.repository import EventRepository

import logging
_STATS_FILE = Path("run_stats.json")
logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


# ---------------------------------------------------------------------------
# Response schemas (Pydantic)
# ---------------------------------------------------------------------------

class EventSummary(BaseModel):
    id: uuid.UUID
    source: str
    title: str
    event_type: str | None
    start_datetime: datetime | None
    end_datetime: datetime | None
    city: str | None
    state: str | None
    distance_miles: float | None
    cost_type: str | None
    event_url: str
    tag_names: list[str] = []
    interest_status: str | None = None

    model_config = {"from_attributes": True}


class SpeakerOut(BaseModel):
    name: str
    title: str | None
    role: str | None

    model_config = {"from_attributes": True}


class CompanyOut(BaseModel):
    name: str
    website: str | None
    linkedin_url: str | None

    model_config = {"from_attributes": True}


class TagOut(BaseModel):
    name: str
    tag_type: str

    model_config = {"from_attributes": True}


class EventDetail(EventSummary):
    description: str | None
    venue_name: str | None
    address: str | None
    zip_code: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    registration_url: str | None
    cost_amount: float | None
    timezone: str | None
    organizers: list[CompanyOut] = []
    sponsors: list[CompanyOut] = []
    tags: list[TagOut] = []
    created_at: datetime
    updated_at: datetime


class RunBody(BaseModel):
    sources: list[str] | None = None


class RunStatus(BaseModel):
    status: str
    summary: dict | None = None
    step: str | None = None


# ---------------------------------------------------------------------------
# Run state (in-memory — replace with a proper task queue for production)
# ---------------------------------------------------------------------------
_run_results: dict[str, Any] = {}


def _save_run_stats(summary: dict) -> None:
    try:
        stats = {"last_run_at": datetime.now(timezone.utc).isoformat(), **summary}
        _STATS_FILE.write_text(json.dumps(stats, indent=2, default=str))
    except Exception as exc:
        logger.warning("Could not save run stats: %s", exc)


async def _do_run(run_id: str, source_filter: str | None):
    def _progress(msg: str) -> None:
        _run_results[run_id]["step"] = msg

    try:
        settings = get_settings()
        crew = AgentCrew(settings)
        _run_results[run_id]["step"] = "Starting…"
        summary = await crew.run(source_filter=source_filter, progress_callback=_progress)
        _run_results[run_id] = {"status": "complete", "summary": summary, "step": None}
        _save_run_stats(summary)
    except Exception as exc:
        _run_results[run_id] = {"status": "error", "summary": {"error": str(exc)}, "step": None}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/tags")
async def list_tags(session: AsyncSession = Depends(get_session)):
    repo = EventRepository(session)
    return await repo.list_tags_with_counts()


@router.get("/events", response_model=list[EventSummary])
async def list_events(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    q: str | None = None,
    event_type: str | None = None,
    source: str | None = None,
    tag: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    max_distance_miles: float | None = None,
    free_only: bool = False,
    hide_noted: bool = True,
    session: AsyncSession = Depends(get_session),
):
    repo = EventRepository(session)
    events = await repo.list_events(
        page=page,
        limit=limit,
        search=q,
        event_type=event_type,
        source=source,
        tag=tag,
        from_date=from_date,
        to_date=to_date,
        max_distance_miles=max_distance_miles,
        free_only=free_only,
        hide_noted=hide_noted,
    )
    summaries = []
    for e in events:
        s = EventSummary.model_validate(e)
        s.tag_names = [t.name for t in e.tags]
        s.interest_status = e.interest.status.value if e.interest else None
        summaries.append(s)
    return summaries


@router.get("/events/count")
async def count_events(
    q: str | None = None,
    event_type: str | None = None,
    source: str | None = None,
    tag: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    max_distance_miles: float | None = None,
    free_only: bool = False,
    hide_noted: bool = True,
    session: AsyncSession = Depends(get_session),
):
    repo = EventRepository(session)
    total = await repo.count_events(
        search=q,
        event_type=event_type,
        source=source,
        tag=tag,
        from_date=from_date,
        to_date=to_date,
        max_distance_miles=max_distance_miles,
        free_only=free_only,
        hide_noted=hide_noted,
    )
    return {"total": total}


@router.get("/events/export.ics")
async def export_ics(
    from_date: datetime | None = None,
    event_type: str | None = None,
    source: str | None = None,
    tag: str | None = None,
    interest_statuses: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    repo = EventRepository(session)
    statuses = [s.strip() for s in interest_statuses.split(",")] if interest_statuses else None
    events = await repo.list_events(
        page=1, limit=500,
        from_date=from_date or datetime.now(timezone.utc),
        event_type=event_type, source=source, tag=tag,
        hide_noted=True,
        interest_statuses=statuses,
    )
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Attendable//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    ]
    for e in events:
        if not e.start_datetime:
            continue
        dtstart = _ical_dt(e.start_datetime)
        dtend   = _ical_dt(e.end_datetime) if e.end_datetime else dtstart
        lines += [
            "BEGIN:VEVENT",
            f"UID:{e.source}-{e.source_id}@attendable",
            f"DTSTART:{dtstart}", f"DTEND:{dtend}",
            f"SUMMARY:{_ical_esc(e.title)}",
            f"URL:{e.event_url or ''}",
        ]
        if e.description:
            lines.append(f"DESCRIPTION:{_ical_esc(e.description[:500])}")
        loc = ", ".join(filter(None, [e.venue_name, e.city, e.state]))
        if loc:
            lines.append(f"LOCATION:{_ical_esc(loc)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return Response(
        "\r\n".join(lines) + "\r\n",
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=attendable.ics"},
    )


def _ical_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ical_esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


@router.get("/events/{event_id}", response_model=EventDetail)
async def get_event(event_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    repo = EventRepository(session)
    event = await repo.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    detail = EventDetail.model_validate(event)

    # Manually load relations (lazy loading not available with async)
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from event_agent.db.models import Event

    result = await session.execute(
        select(Event)
        .options(
            selectinload(Event.organizers),
            selectinload(Event.sponsors),
            selectinload(Event.tags),
            selectinload(Event.speakers),
        )
        .where(Event.id == event_id)
    )
    full_event = result.scalar_one_or_none()
    if full_event:
        detail.organizers = [CompanyOut.model_validate(c) for c in full_event.organizers]
        detail.sponsors = [CompanyOut.model_validate(c) for c in full_event.sponsors]
        detail.tags = [TagOut.model_validate(t) for t in full_event.tags]

    return detail


class InterestBody(BaseModel):
    status: str | None = None  # "noted" | "interested" | "attending" | null to clear


@router.patch("/events/{event_id}/interest", status_code=204)
async def set_interest(
    event_id: uuid.UUID,
    body: InterestBody,
    session: AsyncSession = Depends(get_session),
):
    repo = EventRepository(session)
    if not await repo.get_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    if body.status is None:
        await repo.clear_interest(event_id)
    else:
        await repo.set_interest(event_id, body.status)


@router.post("/run", response_model=RunStatus)
async def trigger_run(body: RunBody, background_tasks: BackgroundTasks):
    import uuid as _uuid
    run_id = str(_uuid.uuid4())
    source_filter = body.sources[0] if body.sources and len(body.sources) == 1 else None
    _run_results[run_id] = {"status": "running", "summary": None}
    background_tasks.add_task(_do_run, run_id, source_filter)
    return RunStatus(status="running", summary={"run_id": run_id})


@router.get("/run/{run_id}", response_model=RunStatus)
async def get_run_status(run_id: str):
    result = _run_results.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunStatus(**result)


@router.get("/stats")
async def get_stats():
    """Return last-run statistics and API key configuration status."""
    stats: dict = {}
    if _STATS_FILE.exists():
        try:
            stats = json.loads(_STATS_FILE.read_text())
        except Exception:
            pass

    s = get_settings()

    # Determine which LLM provider is in use
    model = s.llm_model.lower()
    if "claude" in model or "anthropic" in model:
        llm_name = "Anthropic"
        llm_ok = bool(s.anthropic_api_key or s.llm_api_key)
    elif "gpt" in model or "openai" in model:
        llm_name = "OpenAI"
        llm_ok = bool(s.openai_api_key or s.llm_api_key)
    elif "gemini" in model:
        llm_name = "Google"
        llm_ok = bool(s.gemini_api_key or s.llm_api_key)
    elif "grok" in model or "xai" in model:
        llm_name = "Grok"
        llm_ok = bool(s.xai_api_key or s.llm_api_key)
    elif "mistral" in model:
        llm_name = "Mistral"
        llm_ok = bool(s.mistral_api_key or s.llm_api_key)
    elif "groq" in model:
        llm_name = "Groq"
        llm_ok = bool(s.llm_api_key)
    elif "ollama" in model:
        llm_name = "Ollama"
        llm_ok = bool(s.llm_api_base)
    elif s.llm_api_base:
        llm_name = "Local LLM"
        llm_ok = True   # custom base URL implies it's reachable
    else:
        llm_name = "LLM"
        llm_ok = bool(s.llm_api_key)

    # API keys — only show configured providers (green) + missing critical ones (red)
    api_keys: dict = {}
    if llm_ok:
        api_keys[llm_name] = "active"
    else:
        api_keys["LLM"] = "needs attention"

    if s.brave_api_key:
        api_keys["Brave Search"] = "active"
    if s.serp_api_key:
        api_keys["SerpAPI"] = "active"
    if s.searxng_url:
        api_keys["SearXNG"] = "active"
    if not s.brave_api_key and not s.serp_api_key and not s.searxng_url:
        api_keys["Search"] = "fallback"   # DuckDuckGo silent fallback

    stats["api_status"] = api_keys

    # Active search provider name (for Sources endpoint label)
    if s.brave_api_key:
        search_provider = "Brave Search"
    elif s.serp_api_key:
        search_provider = "SerpAPI"
    elif s.searxng_url:
        search_provider = "SearXNG"
    else:
        search_provider = "DuckDuckGo"

    stats["enabled_sources"] = s.enabled_sources
    stats["search_provider"] = search_provider
    return stats
