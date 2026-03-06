"""APScheduler helpers for the event agent.

Kept in a separate module so both main.py (lifespan) and config.py (PATCH)
can import without creating circular dependencies.
"""
from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


async def scheduled_job() -> None:
    """Full pipeline run triggered by the scheduler."""
    from event_agent.api.routes.events import _do_run, _run_results  # noqa: PLC0415

    run_id = f"sched-{uuid.uuid4()}"
    _run_results[run_id] = {"status": "running", "summary": None}
    logger.info("Scheduled pipeline run starting (run_id=%s)", run_id)
    await _do_run(run_id, None)
    logger.info("Scheduled pipeline run complete (run_id=%s)", run_id)


async def scheduled_cleanup() -> None:
    """Weekly DB cleanup triggered by the scheduler."""
    from event_agent.api.routes.config import _merged        # noqa: PLC0415
    from event_agent.db.engine import get_session_factory    # noqa: PLC0415
    from event_agent.db.repository import EventRepository    # noqa: PLC0415

    cfg = _merged()
    days = int(cfg.get("cleanup_days_past", 30))
    factory = get_session_factory()
    async with factory() as session:
        count = await EventRepository(session).cleanup_past_events(days_past=days)
    logger.info("Scheduled cleanup: deleted %d past events (cutoff: %d days)", count, days)


def build_scheduler(
    enabled: bool, hour: int, minute: int,
    cleanup_enabled: bool = True, cleanup_day_of_week: int = 6, cleanup_hour: int = 3,
) -> AsyncIOScheduler:
    """Create, configure, and start the scheduler."""
    sched = AsyncIOScheduler()
    if enabled:
        sched.add_job(scheduled_job, "cron", hour=hour, minute=minute, id="daily_run")
        logger.info("Scheduler: pipeline run daily at %02d:%02d", hour, minute)
    else:
        logger.info("Scheduler: pipeline job disabled")
    if cleanup_enabled:
        sched.add_job(
            scheduled_cleanup, "cron",
            day_of_week=cleanup_day_of_week, hour=cleanup_hour,
            id="weekly_cleanup",
        )
        logger.info(
            "Scheduler: cleanup weekly on day_of_week=%d at %02d:00",
            cleanup_day_of_week, cleanup_hour,
        )
    else:
        logger.info("Scheduler: cleanup job disabled")
    sched.start()
    return sched


def apply_schedule(sched: AsyncIOScheduler, enabled: bool, hour: int, minute: int) -> None:
    """Dynamically add, remove, or reschedule the daily_run job."""
    job = sched.get_job("daily_run")
    if enabled and job is None:
        sched.add_job(scheduled_job, "cron", hour=hour, minute=minute, id="daily_run")
        logger.info("Scheduler: pipeline job added — daily at %02d:%02d", hour, minute)
    elif enabled and job is not None:
        sched.reschedule_job("daily_run", trigger="cron", hour=hour, minute=minute)
        logger.info("Scheduler: pipeline job rescheduled — daily at %02d:%02d", hour, minute)
    elif not enabled and job is not None:
        sched.remove_job("daily_run")
        logger.info("Scheduler: pipeline job removed")


def apply_cleanup_schedule(
    sched: AsyncIOScheduler, enabled: bool, day_of_week: int, hour: int
) -> None:
    """Dynamically add, remove, or reschedule the weekly_cleanup job."""
    job = sched.get_job("weekly_cleanup")
    if enabled and job is None:
        sched.add_job(
            scheduled_cleanup, "cron",
            day_of_week=day_of_week, hour=hour, id="weekly_cleanup",
        )
        logger.info("Scheduler: cleanup job added — day_of_week=%d at %02d:00", day_of_week, hour)
    elif enabled and job is not None:
        sched.reschedule_job(
            "weekly_cleanup", trigger="cron", day_of_week=day_of_week, hour=hour
        )
        logger.info("Scheduler: cleanup job rescheduled — day_of_week=%d at %02d:00", day_of_week, hour)
    elif not enabled and job is not None:
        sched.remove_job("weekly_cleanup")
        logger.info("Scheduler: cleanup job removed")
