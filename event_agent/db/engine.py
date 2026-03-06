"""Async SQLAlchemy engine and session factory."""
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from event_agent.config.settings import get_settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        if settings.database_url.startswith("sqlite"):
            _engine = create_async_engine(
                settings.database_url,
                echo=False,
                connect_args={"check_same_thread": False},
            )
        else:
            _engine = create_async_engine(
                settings.database_url,
                echo=False,
                pool_pre_ping=True,
            )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI / standalone use."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
