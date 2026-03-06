"""CLI entry point for event-agent."""
import asyncio
import logging
import tomllib
from pathlib import Path
import click
import uvicorn

_VERSION = tomllib.loads((Path(__file__).parent / "pyproject.toml").read_text())["project"]["version"]


def _configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Silence noisy third-party loggers unless in verbose mode
    if not verbose:
        for noisy in ("httpx", "httpcore", "hpack", "asyncio", "litellm", "LiteLLM"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


@click.group()
def cli():
    """Attendable - AI Powered Event Discovery."""


@cli.command()
@click.option("--source", default=None, help="Run a single scraper source (e.g. luma, web_search)")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show debug-level logs")
def run(source: str | None, verbose: bool):
    """Run the full agent crew pipeline (or a single source)."""
    _configure_logging(verbose)
    from event_agent.agents.crew import AgentCrew
    from event_agent.config.settings import get_settings

    settings = get_settings()
    crew = AgentCrew(settings)
    try:
        summary = asyncio.run(crew.run(source_filter=source))
    except Exception:
        import traceback
        click.echo("\n── Pipeline failed ──────────────────────", err=True)
        click.echo(traceback.format_exc(), err=True)
        raise SystemExit(1)

    click.echo("\n── Run complete ─────────────────────────")
    for key, value in summary.items():
        click.echo(f"  {key:<25} {value}")
    click.echo("─────────────────────────────────────────")


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--reload", is_flag=True, default=False)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show debug-level logs")
def serve(host: str, port: int, reload: bool, verbose: bool):
    """Start the FastAPI server."""
    _configure_logging(verbose)
    click.echo(
        "\n"
        "  ╔══════════════════════════════════════╗\n"
        f"  ║{f'Attendable  v{_VERSION}'.center(38)}║\n"
        f"  ║{'AI Powered Event Discovery'.center(38)}║\n"
        "  ╚══════════════════════════════════════╝\n"
        f"  → http://localhost:{port}\n"
    )
    uvicorn.run(
        "event_agent.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if verbose else "info",
    )


@cli.group()
def db():
    """Database management commands."""


@db.command("init")
def db_init():
    """Run alembic upgrade head to create/update tables."""
    import subprocess
    result = subprocess.run(["alembic", "upgrade", "head"], check=True)
    click.echo("Database initialized." if result.returncode == 0 else "Migration failed.")


@db.command("migrate")
@click.option("--message", "-m", required=True, help="Migration message")
def db_migrate(message: str):
    """Generate a new Alembic migration."""
    import subprocess
    subprocess.run(["alembic", "revision", "--autogenerate", "-m", message], check=True)


@db.command("cleanup")
@click.option("--days", default=30, show_default=True, help="Delete events that ended more than N days ago.")
def db_cleanup(days: int):
    """Remove past events from the database."""
    async def _run():
        from event_agent.db.engine import get_session_factory
        from event_agent.db.repository import EventRepository
        factory = get_session_factory()
        async with factory() as session:
            repo = EventRepository(session)
            count = await repo.cleanup_past_events(days_past=days)
            click.echo(f"Deleted {count} past event(s) (cutoff: {days} days ago).")
    asyncio.run(_run())


if __name__ == "__main__":
    cli()
