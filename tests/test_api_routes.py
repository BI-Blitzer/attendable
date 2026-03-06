"""Tests for FastAPI event and config routes."""
import uuid
import pytest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport

from event_agent.api.main import create_app
from event_agent.db.engine import get_session


FAKE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _fake_event(**overrides):
    """Build a fake Event-like object compatible with Pydantic from_attributes."""
    base = SimpleNamespace(
        id=FAKE_ID,
        source="luma",
        source_id="evt-001",
        title="NJ AI Summit",
        event_type="physical",
        start_datetime=datetime(2026, 6, 10, 14, 0, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc),
        city="Newark",
        state="NJ",
        distance_miles=25.0,
        cost_type="free",
        event_url="https://lu.ma/e/nj-ai-summit",
        description="An AI summit",
        venue_name="Newark Convention Center",
        address="100 Main St",
        zip_code="07102",
        country="USA",
        latitude=40.73,
        longitude=-74.17,
        registration_url=None,
        cost_amount=None,
        timezone="America/New_York",
        organizers=[],
        sponsors=[],
        tags=[],
        speakers=[],
        interest=None,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        canonical_event_id=None,
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
    monkeypatch.setenv("CENTER_ZIP", "10001")
    from event_agent.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_session():
    """Async session mock — execute() returns a result with scalar_one_or_none()."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = _fake_event()
    session.execute.return_value = result_mock
    return session


@pytest.fixture
def app(mock_session):
    application = create_app()

    async def override_get_session():
        yield mock_session

    application.dependency_overrides[get_session] = override_get_session
    return application


# ---------------------------------------------------------------------------
# GET /events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_events_returns_list(app):
    fake = _fake_event()
    with patch("event_agent.api.routes.events.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.list_events.return_value = [fake]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/events")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "NJ AI Summit"
    assert data[0]["source"] == "luma"
    assert data[0]["city"] == "Newark"


@pytest.mark.asyncio
async def test_list_events_empty(app):
    with patch("event_agent.api.routes.events.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.list_events.return_value = []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/events")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_events_filter_params_forwarded(app):
    """Query params are forwarded to repo.list_events."""
    with patch("event_agent.api.routes.events.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.list_events.return_value = []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/events?q=summit&source=luma&free_only=true&limit=5")

    assert resp.status_code == 200
    call_kwargs = mock_repo.list_events.call_args.kwargs
    assert call_kwargs["search"] == "summit"
    assert call_kwargs["source"] == "luma"
    assert call_kwargs["free_only"] is True
    assert call_kwargs["limit"] == 5


# ---------------------------------------------------------------------------
# GET /events/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_event_returns_detail(app, mock_session):
    fake = _fake_event()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fake
    mock_session.execute.return_value = result_mock

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/events/{FAKE_ID}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(FAKE_ID)
    assert data["title"] == "NJ AI Summit"
    assert data["venue_name"] == "Newark Convention Center"
    assert data["organizers"] == []
    assert data["tags"] == []


@pytest.mark.asyncio
async def test_get_event_not_found(app, mock_session):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result_mock

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/events/{uuid.uuid4()}")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /run  &  GET /run/{run_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_run_returns_running(app):
    with patch("event_agent.api.routes.events._do_run", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/run", json={})

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert "run_id" in data["summary"]


@pytest.mark.asyncio
async def test_get_run_status_not_found(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/run/does-not-exist")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /config  &  PATCH /config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_config_returns_defaults(app):
    with patch("event_agent.api.routes.config._load_overrides", return_value={}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/config")

    assert resp.status_code == 200
    data = resp.json()
    assert data["center_zip"] == "10001"
    assert data["radius_miles"] == 120
    assert "luma" in data["enabled_sources"]
    assert data["llm_model"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_patch_config_updates_fields(app):
    saved: dict = {}

    with (
        patch("event_agent.api.routes.config._load_overrides", side_effect=lambda: saved.copy()),
        patch("event_agent.api.routes.config._save_overrides", side_effect=saved.update),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/config", json={"center_zip": "10001", "radius_miles": 50})

    assert resp.status_code == 200
    data = resp.json()
    assert data["center_zip"] == "10001"
    assert data["radius_miles"] == 50
    assert saved["center_zip"] == "10001"
    assert saved["radius_miles"] == 50


@pytest.mark.asyncio
async def test_get_config_returns_wizard_completed_false_by_default(app):
    with patch("event_agent.api.routes.config._load_overrides", return_value={}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/config")

    assert resp.status_code == 200
    assert resp.json()["wizard_completed"] is False


@pytest.mark.asyncio
async def test_patch_config_wizard_completed(app):
    saved: dict = {}

    with (
        patch("event_agent.api.routes.config._load_overrides", side_effect=lambda: saved.copy()),
        patch("event_agent.api.routes.config._save_overrides", side_effect=saved.update),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch("/config", json={"wizard_completed": True})

    assert resp.status_code == 200
    assert resp.json()["wizard_completed"] is True
    assert saved["wizard_completed"] is True


# ---------------------------------------------------------------------------
# GET /setup/status — wizard_completed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_setup_status_wizard_completed_defaults_false(app):
    with patch("event_agent.api.routes.setup._load_overrides", return_value={}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/setup/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["wizard_completed"] is False
    assert "needs_setup" in data
    assert "configured" in data


@pytest.mark.asyncio
async def test_setup_status_wizard_completed_true(app):
    with patch("event_agent.api.routes.setup._load_overrides", return_value={"wizard_completed": True}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/setup/status")

    assert resp.status_code == 200
    assert resp.json()["wizard_completed"] is True


# ---------------------------------------------------------------------------
# GET /events/export.ics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_ics_returns_calendar(app):
    fake = _fake_event()
    with patch("event_agent.api.routes.events.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.list_events.return_value = [fake]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/events/export.ics")

    assert resp.status_code == 200
    assert "text/calendar" in resp.headers["content-type"]
    text = resp.text
    assert "BEGIN:VCALENDAR" in text
    assert "BEGIN:VEVENT" in text
    assert "NJ AI Summit" in text


@pytest.mark.asyncio
async def test_export_ics_interest_statuses_forwarded(app):
    with patch("event_agent.api.routes.events.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.list_events.return_value = []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/events/export.ics?interest_statuses=interested,attending")

    assert resp.status_code == 200
    call_kwargs = mock_repo.list_events.call_args.kwargs
    assert call_kwargs["interest_statuses"] == ["interested", "attending"]


@pytest.mark.asyncio
async def test_export_ics_no_interest_filter_passes_none(app):
    with patch("event_agent.api.routes.events.EventRepository") as MockRepo:
        mock_repo = AsyncMock()
        MockRepo.return_value = mock_repo
        mock_repo.list_events.return_value = []

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/events/export.ics")

    assert resp.status_code == 200
    call_kwargs = mock_repo.list_events.call_args.kwargs
    assert call_kwargs["interest_statuses"] is None
