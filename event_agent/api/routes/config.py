"""Config API routes — read and patch runtime settings, persisted to config.json."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from event_agent.config.settings import get_settings

router = APIRouter(prefix="/config", tags=["config"])

_CONFIG_FILE = Path("config.json")

_PATCHABLE = (
    "center_zip", "radius_miles", "center_lat", "center_lon",
    "enabled_sources", "search_keywords", "vendor_virtual_keywords",
    "user_keywords",
    "llm_model", "llm_api_base",
    "schedule_enabled", "schedule_hour", "schedule_minute",
    "cleanup_schedule_enabled", "cleanup_day_of_week",
    "cleanup_schedule_hour", "cleanup_days_past",
    "searxng_url",
    "wizard_completed",
)


def _load_overrides() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_overrides(overrides: dict) -> None:
    _CONFIG_FILE.write_text(json.dumps(overrides, indent=2))


def _merged() -> dict:
    s = get_settings()
    o = _load_overrides()
    return {
        "center_zip":              o.get("center_zip",              s.center_zip),
        "radius_miles":            o.get("radius_miles",            s.radius_miles),
        "center_lat":              o.get("center_lat",              s.center_lat),
        "center_lon":              o.get("center_lon",              s.center_lon),
        "enabled_sources":         o.get("enabled_sources",         s.enabled_sources),
        "search_keywords":         o.get("search_keywords",         s.search_keywords),
        "vendor_virtual_keywords": o.get("vendor_virtual_keywords", s.vendor_virtual_keywords),
        "user_keywords":           o.get("user_keywords",           s.user_keywords),
        "llm_model":               o.get("llm_model",               s.llm_model),
        "llm_api_base":            o.get("llm_api_base",            s.llm_api_base),
        "schedule_enabled":          o.get("schedule_enabled",          s.schedule_enabled),
        "schedule_hour":             o.get("schedule_hour",             s.schedule_hour),
        "schedule_minute":           o.get("schedule_minute",           s.schedule_minute),
        "cleanup_schedule_enabled":  o.get("cleanup_schedule_enabled",  s.cleanup_schedule_enabled),
        "cleanup_day_of_week":       o.get("cleanup_day_of_week",       s.cleanup_day_of_week),
        "cleanup_schedule_hour":     o.get("cleanup_schedule_hour",     s.cleanup_schedule_hour),
        "cleanup_days_past":         o.get("cleanup_days_past",         s.cleanup_days_past),
        "searxng_url":               o.get("searxng_url",               s.searxng_url),
        "wizard_completed":          o.get("wizard_completed",          s.wizard_completed),
    }


def _next_run_at(request: Request | None) -> str | None:
    if request is None:
        return None
    sched = getattr(request.app.state, "scheduler", None)
    if sched is None:
        return None
    job = sched.get_job("daily_run")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None


def _next_cleanup_at(request: Request | None) -> str | None:
    if request is None:
        return None
    sched = getattr(request.app.state, "scheduler", None)
    if sched is None:
        return None
    job = sched.get_job("weekly_cleanup")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None


class ConfigOut(BaseModel):
    center_zip: str
    radius_miles: int
    center_lat: float | None = None
    center_lon: float | None = None
    enabled_sources: list[str]
    search_keywords: list[str]
    vendor_virtual_keywords: list[str]
    user_keywords: list[str]
    llm_model: str
    llm_api_base: str
    schedule_enabled: bool
    schedule_hour: int
    schedule_minute: int
    cleanup_schedule_enabled: bool
    cleanup_day_of_week: int
    cleanup_schedule_hour: int
    cleanup_days_past: int
    searxng_url: str
    wizard_completed: bool = False
    next_run_at: str | None = None
    next_cleanup_at: str | None = None


class ConfigPatch(BaseModel):
    center_zip: str | None = None
    radius_miles: int | None = None
    center_lat: float | None = None
    center_lon: float | None = None
    enabled_sources: list[str] | None = None
    search_keywords: list[str] | None = None
    vendor_virtual_keywords: list[str] | None = None
    user_keywords: list[str] | None = None
    llm_model: str | None = None
    llm_api_base: str | None = None
    schedule_enabled: bool | None = None
    schedule_hour: int | None = None
    schedule_minute: int | None = None
    cleanup_schedule_enabled: bool | None = None
    cleanup_day_of_week: int | None = None
    cleanup_schedule_hour: int | None = None
    cleanup_days_past: int | None = None
    searxng_url: str | None = None
    wizard_completed: bool | None = None


@router.get("", response_model=ConfigOut)
async def get_config(request: Request):
    return ConfigOut(
        **_merged(),
        next_run_at=_next_run_at(request),
        next_cleanup_at=_next_cleanup_at(request),
    )


@router.patch("", response_model=ConfigOut)
async def patch_config(patch: ConfigPatch, request: Request):
    overrides = _load_overrides()
    schedule_changed = False

    _PIPELINE_FIELDS = {"schedule_enabled", "schedule_hour", "schedule_minute"}
    _CLEANUP_FIELDS  = {"cleanup_schedule_enabled", "cleanup_day_of_week",
                        "cleanup_schedule_hour", "cleanup_days_past"}
    schedule_changed = False
    cleanup_changed  = False

    for field in _PATCHABLE:
        value = getattr(patch, field, None)
        if value is not None:
            overrides[field] = value
            if field in _PIPELINE_FIELDS:
                schedule_changed = True
            if field in _CLEANUP_FIELDS:
                cleanup_changed = True

    _save_overrides(overrides)

    sched = getattr(request.app.state, "scheduler", None)
    if sched:
        cfg = _merged()
        if schedule_changed:
            from event_agent.api.scheduler import apply_schedule  # noqa: PLC0415
            apply_schedule(
                sched,
                enabled=cfg["schedule_enabled"],
                hour=cfg["schedule_hour"],
                minute=cfg["schedule_minute"],
            )
        if cleanup_changed:
            from event_agent.api.scheduler import apply_cleanup_schedule  # noqa: PLC0415
            apply_cleanup_schedule(
                sched,
                enabled=cfg["cleanup_schedule_enabled"],
                day_of_week=cfg["cleanup_day_of_week"],
                hour=cfg["cleanup_schedule_hour"],
            )

    return ConfigOut(
        **_merged(),
        next_run_at=_next_run_at(request),
        next_cleanup_at=_next_cleanup_at(request),
    )
