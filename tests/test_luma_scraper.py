"""Unit tests for the Luma scraper (api2.luma.com direct API)."""
import pytest
from pytest_httpx import HTTPXMock

from event_agent.scrapers.luma import LumaScraper, API_BASE, LUMA_WEB_BASE
from event_agent.scrapers.base import RawEvent


BOOTSTRAP_RESPONSE = {
    "places": [
        {
            "place": {
                "api_id": "discplace-nyc",
                "slug": "nyc",
                "name": "New York",
                "coordinate": {"latitude": 40.7128, "longitude": -74.0060},  # ~0 mi from NYC center
            }
        },
        {
            "place": {
                "api_id": "discplace-la",
                "slug": "los-angeles",
                "name": "Los Angeles",
                "coordinate": {"latitude": 34.0522, "longitude": -118.2437},  # ~2700 mi away
            }
        },
    ]
}

PAGINATED_EVENTS_PAGE1 = {
    "entries": [
        {
            "event": {
                "api_id": "evt-001",
                "name": "NJ AI Summit",
                "start_at": "2026-06-10T14:00:00.000Z",
                "end_at": "2026-06-10T18:00:00.000Z",
                "location_type": "offline",
                "url": "nj-ai-summit",
                "geo_address_info": {
                    "full_address": "100 Main St, Newark, NJ 07102, USA",
                    "city_state": "Newark, NJ",
                },
            }
        },
        {
            "event": {
                "api_id": "evt-002",
                "name": "NYC Virtual Data Meetup",
                "start_at": "2026-07-01T18:00:00.000Z",
                "end_at": "2026-07-01T20:00:00.000Z",
                "location_type": "online",
                "url": "nyc-virtual-data-meetup",
                "geo_address_info": {},
            }
        },
    ],
    "has_more": True,
    "next_cursor": "cursor-abc",
}

PAGINATED_EVENTS_PAGE2 = {
    "entries": [
        {
            "event": {
                "api_id": "evt-003",
                "name": "Philly BI Conference",
                "start_at": "2026-08-15T09:00:00.000Z",
                "end_at": "2026-08-15T17:00:00.000Z",
                "location_type": "offline",
                "url": "philly-bi-conference",
                "geo_address_info": {
                    "full_address": "200 Convention Ave, Philadelphia, PA 19103",
                },
            }
        }
    ],
    "has_more": False,
    "next_cursor": None,
}


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
    from event_agent.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_fetch_filters_distant_places(httpx_mock: HTTPXMock):
    """Only NYC (49 mi) should be used; LA (2700 mi) should be skipped."""
    httpx_mock.add_response(json=BOOTSTRAP_RESPONSE)   # bootstrap
    httpx_mock.add_response(json={**PAGINATED_EVENTS_PAGE1, "has_more": False})  # NYC events

    scraper = LumaScraper()
    events = await scraper.fetch(["technology"])

    assert len(events) == 2  # only NYC events, LA was filtered


@pytest.mark.asyncio
async def test_physical_event_parsed(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=BOOTSTRAP_RESPONSE)
    httpx_mock.add_response(json={**PAGINATED_EVENTS_PAGE1, "has_more": False})

    scraper = LumaScraper()
    events = await scraper.fetch(["technology"])
    evt = events[0]

    assert evt.source == "luma"
    assert evt.source_id == "evt-001"
    assert evt.title == "NJ AI Summit"
    assert evt.is_virtual is False
    assert evt.location_text == "100 Main St, Newark, NJ 07102, USA"
    assert evt.url == f"{LUMA_WEB_BASE}/e/nj-ai-summit"
    assert evt.start_datetime == "2026-06-10T14:00:00.000Z"


@pytest.mark.asyncio
async def test_virtual_event_parsed(httpx_mock: HTTPXMock):
    httpx_mock.add_response(json=BOOTSTRAP_RESPONSE)
    httpx_mock.add_response(json={**PAGINATED_EVENTS_PAGE1, "has_more": False})

    scraper = LumaScraper()
    events = await scraper.fetch(["technology"])
    evt = events[1]

    assert evt.source_id == "evt-002"
    assert evt.is_virtual is True
    assert evt.location_text == "Online"


@pytest.mark.asyncio
async def test_pagination_followed(httpx_mock: HTTPXMock):
    """Scraper should follow has_more/next_cursor to fetch all pages."""
    httpx_mock.add_response(json=BOOTSTRAP_RESPONSE)        # bootstrap
    httpx_mock.add_response(json=PAGINATED_EVENTS_PAGE1)     # page 1 (has_more=True)
    httpx_mock.add_response(json=PAGINATED_EVENTS_PAGE2)     # page 2 (has_more=False)

    scraper = LumaScraper()
    events = await scraper.fetch(["technology"])

    assert len(events) == 3
    ids = {e.source_id for e in events}
    assert ids == {"evt-001", "evt-002", "evt-003"}


@pytest.mark.asyncio
async def test_dedup_across_places(httpx_mock: HTTPXMock):
    """Same event returned by two places should only appear once."""
    two_places = {
        "places": [
            {"place": {"api_id": "discplace-nyc", "slug": "nyc", "coordinate": {"latitude": 40.71, "longitude": -74.01}}},
            {"place": {"api_id": "discplace-phi", "slug": "philly", "coordinate": {"latitude": 39.95, "longitude": -75.17}}},
        ]
    }
    single_event = {"entries": [PAGINATED_EVENTS_PAGE1["entries"][0]], "has_more": False}

    httpx_mock.add_response(json=two_places)    # bootstrap
    httpx_mock.add_response(json=single_event)  # NYC: evt-001
    httpx_mock.add_response(json=single_event)  # Philly: evt-001 again

    scraper = LumaScraper()
    events = await scraper.fetch(["technology"])

    assert len(events) == 1
