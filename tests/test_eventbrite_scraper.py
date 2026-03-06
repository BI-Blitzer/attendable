"""Unit tests for the Eventbrite Playwright scraper."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from event_agent.scrapers.base import RawEvent
from event_agent.scrapers.eventbrite import (
    EventbriteScraper,
    _keyword_slug,
    _parse_city_state,
    _zip_to_location_slug,
)

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_RAW_ITEMS = [
    {
        "id": "123456789",
        "title": "NJ Tech Summit 2026",
        "url": "https://www.eventbrite.com/e/nj-tech-summit-2026-tickets-123456789",
        "startDt": "2026-06-15T13:00:00Z",
        "endDt": "2026-06-15T18:00:00Z",
        "locationText": "Convention Center, Atlantic City, NJ",
        "city": "Atlantic City",
        "state": "NJ",
        "isOnline": False,
        "description": "A premier tech conference.",
    },
    {
        "id": "987654321",
        "title": "Virtual BI Workshop",
        "url": "https://www.eventbrite.com/e/virtual-bi-workshop-tickets-987654321",
        "startDt": "2026-07-10T18:00:00Z",
        "endDt": "2026-07-10T20:00:00Z",
        "locationText": None,
        "city": None,
        "state": None,
        "isOnline": True,
        "description": "Online business intelligence workshop.",
    },
]

SAMPLE_HREFS = [
    "https://www.eventbrite.com/e/nj-tech-summit-2026-tickets-123456789",
    "https://www.eventbrite.com/e/virtual-bi-workshop-tickets-987654321",
    "https://www.eventbrite.com/e/data-analytics-conference-tickets-111222333",
]


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
    from event_agent.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_playwright_mock(hrefs: list[str]):
    """Build a minimal async_playwright context manager mock.

    evaluate() is called twice per keyword:
      1. title check  → returns page title string
      2. href harvest → returns list[str] of event URLs
    """
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(side_effect=["Test Events | Eventbrite", hrefs])

    mock_ctx = AsyncMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_ctx)

    mock_pw = MagicMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


# ---------------------------------------------------------------------------
# Tests: pure helper functions
# ---------------------------------------------------------------------------

def test_zip_to_location_slug_nj():
    assert _zip_to_location_slug("07001") == "nj--new-jersey"


def test_zip_to_location_slug_ny():
    assert _zip_to_location_slug("10001") == "ny--new-york"


def test_zip_to_location_slug_ca():
    assert _zip_to_location_slug("90210") == "ca--california"


def test_keyword_slug_simple():
    assert _keyword_slug("Technology Conference") == "technology-conference"


def test_parse_city_state_csv():
    city, state = _parse_city_state("Atlantic City, NJ")
    assert city == "Atlantic City"
    assert state == "NJ"


def test_parse_city_state_empty():
    assert _parse_city_state("") == (None, None)
    assert _parse_city_state("OnlineOnly") == (None, None)


# ---------------------------------------------------------------------------
# Tests: _parse_items (pure logic, no Playwright)
# ---------------------------------------------------------------------------

def test_parse_items_returns_raw_events():
    scraper = EventbriteScraper()
    events = scraper._parse_items(SAMPLE_RAW_ITEMS, set())
    assert len(events) == 2
    assert all(isinstance(e, RawEvent) for e in events)


def test_parse_items_physical_event():
    scraper = EventbriteScraper()
    phys = scraper._parse_items(SAMPLE_RAW_ITEMS, set())[0]

    assert phys.source == "eventbrite"
    assert phys.source_id == "123456789"
    assert phys.title == "NJ Tech Summit 2026"
    assert phys.is_virtual is False
    assert phys.city == "Atlantic City"
    assert phys.state == "NJ"
    assert phys.start_datetime == "2026-06-15T13:00:00Z"


def test_parse_items_virtual_event():
    scraper = EventbriteScraper()
    virt = scraper._parse_items(SAMPLE_RAW_ITEMS, set())[1]

    assert virt.source_id == "987654321"
    assert virt.is_virtual is True
    assert virt.location_text is None


def test_parse_items_deduplicates():
    scraper = EventbriteScraper()
    seen = {"123456789"}
    events = scraper._parse_items(SAMPLE_RAW_ITEMS, seen)
    assert len(events) == 1
    assert events[0].source_id == "987654321"


# ---------------------------------------------------------------------------
# Tests: _parse_hrefs (pure logic, no Playwright)
# ---------------------------------------------------------------------------

def test_parse_hrefs_returns_raw_events():
    scraper = EventbriteScraper()
    events = scraper._parse_hrefs(SAMPLE_HREFS, set())
    assert len(events) == 3
    assert all(isinstance(e, RawEvent) for e in events)


def test_parse_hrefs_extracts_id():
    scraper = EventbriteScraper()
    events = scraper._parse_hrefs(SAMPLE_HREFS, set())
    assert events[0].source_id == "123456789"
    assert events[1].source_id == "987654321"
    assert events[2].source_id == "111222333"


def test_parse_hrefs_title_from_slug():
    scraper = EventbriteScraper()
    events = scraper._parse_hrefs(SAMPLE_HREFS, set())
    # Slug "nj-tech-summit-2026-tickets-123456789" → "Nj Tech Summit 2026"
    assert "Tech Summit" in events[0].title
    assert "Bi Workshop" in events[1].title or "Workshop" in events[1].title


def test_parse_hrefs_deduplicates_by_id():
    scraper = EventbriteScraper()
    seen = {"123456789"}
    events = scraper._parse_hrefs(SAMPLE_HREFS, seen)
    assert len(events) == 2
    ids = {e.source_id for e in events}
    assert "123456789" not in ids


def test_parse_hrefs_deduplicates_same_url():
    scraper = EventbriteScraper()
    dupes = SAMPLE_HREFS + SAMPLE_HREFS
    events = scraper._parse_hrefs(dupes, set())
    assert len(events) == 3


def test_parse_hrefs_skips_short_ids():
    scraper = EventbriteScraper()
    bad_hrefs = [
        "https://www.eventbrite.com/e/some-event-tickets-123",  # ID too short
        "https://www.eventbrite.com/e/real-event-tickets-123456789",
    ]
    events = scraper._parse_hrefs(bad_hrefs, set())
    assert len(events) == 1
    assert events[0].source_id == "123456789"


def test_parse_hrefs_strips_query_params():
    scraper = EventbriteScraper()
    hrefs = ["https://www.eventbrite.com/e/some-event-tickets-999888777?aff=erelexpmlt"]
    events = scraper._parse_hrefs(hrefs, set())
    assert len(events) == 1
    assert "?" not in events[0].url


# ---------------------------------------------------------------------------
# Tests: fetch() with mocked Playwright
# ---------------------------------------------------------------------------

def _playwright_patches(mock_cm):
    """Return a context manager that patches both playwright and stealth."""
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch("playwright.async_api.async_playwright", return_value=mock_cm))
    mock_stealth = MagicMock()
    mock_stealth.apply_stealth_async = AsyncMock()
    stack.enter_context(patch("playwright_stealth.Stealth", return_value=mock_stealth))
    return stack


@pytest.mark.asyncio
async def test_fetch_returns_raw_events():
    mock_cm = _make_playwright_mock(SAMPLE_HREFS)
    with _playwright_patches(mock_cm):
        scraper = EventbriteScraper()
        events = await scraper.fetch(["technology conference"])

    assert len(events) == 3
    assert all(isinstance(e, RawEvent) for e in events)


@pytest.mark.asyncio
async def test_fetch_handles_empty_page():
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(side_effect=["Test Events | Eventbrite", []])
    mock_ctx = AsyncMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)
    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_ctx)
    mock_pw = MagicMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_pw)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with _playwright_patches(mock_cm):
        scraper = EventbriteScraper()
        events = await scraper.fetch(["obscure topic xyz"])

    assert events == []


@pytest.mark.asyncio
async def test_fetch_handles_browser_failure():
    """If the browser session throws, fetch() returns [] gracefully."""
    bad_cm = AsyncMock()
    bad_cm.__aenter__ = AsyncMock(side_effect=Exception("browser crashed"))
    bad_cm.__aexit__ = AsyncMock(return_value=False)

    with _playwright_patches(bad_cm):
        scraper = EventbriteScraper()
        events = await scraper.fetch(["technology"])

    assert events == []
