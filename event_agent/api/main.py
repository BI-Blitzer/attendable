"""FastAPI application factory."""
import logging
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI

from event_agent.api.routes import backup as backup_router
from event_agent.api.routes import config as config_router
from event_agent.api.routes import events as events_router
from event_agent.api.routes import setup as setup_router
from event_agent.api.routes import ui as ui_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the database schema is up to date before accepting traffic.
    # On a fresh install this creates all tables; on subsequent starts it's a no-op.
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info("DB schema up to date")
        else:
            logger.warning("alembic upgrade failed: %s", result.stderr.strip())
    except Exception as exc:
        logger.warning("DB auto-init skipped: %s", exc)

    from event_agent.api.scheduler import build_scheduler  # noqa: PLC0415
    from event_agent.api.routes.config import _merged      # noqa: PLC0415

    cfg = _merged()
    app.state.scheduler = build_scheduler(
        enabled=cfg.get("schedule_enabled", True),
        hour=cfg.get("schedule_hour", 6),
        minute=cfg.get("schedule_minute", 0),
        cleanup_enabled=cfg.get("cleanup_schedule_enabled", True),
        cleanup_day_of_week=cfg.get("cleanup_day_of_week", 6),
        cleanup_hour=cfg.get("cleanup_schedule_hour", 3),
    )
    yield
    app.state.scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


def create_app() -> FastAPI:
    application = FastAPI(
        title="Attendable",
        description="AI Powered Event Discovery",
        version="0.5.0a1",
        lifespan=lifespan,
    )
    application.include_router(ui_router.router)
    application.include_router(events_router.router)
    application.include_router(config_router.router)
    application.include_router(setup_router.router)
    application.include_router(backup_router.router)
    return application


app = create_app()
