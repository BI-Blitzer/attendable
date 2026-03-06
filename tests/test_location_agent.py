"""Unit tests for the LocationAgent radius filter and geocoding."""
import pytest
from unittest.mock import MagicMock, patch

from event_agent.scrapers.base import RawEvent


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test")
    monkeypatch.setenv("CENTER_ZIP", "10001")
    from event_agent.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_event(location_text: str | None = None, is_virtual: bool | None = None) -> RawEvent:
    return RawEvent(
        source="eventbrite",
        source_id="test-1",
        title="Test Event",
        url="https://example.com/event",
        location_text=location_text,
        is_virtual=is_virtual,
    )


# Fixed coordinates for known test locations
_COORDS = {
    "10001, USA": (40.7128, -74.0060),                                      # Midtown Manhattan (center)
    "New York Convention Center, New York, NY": (40.7549, -74.0020),        # ~3 mi
    "Los Angeles Convention Center, Los Angeles, CA": (34.0401, -118.2695), # ~2700 mi
}


def _mock_rate_limited_geocode(text: str, **_):
    coords = _COORDS.get(text)
    if coords:
        loc = MagicMock()
        loc.latitude, loc.longitude = coords
        return loc
    return None


@pytest.fixture
def location_agent():
    import event_agent.agents.location_agent as la_module
    la_module._geocode.cache_clear()
    la_module._zip_centroid.cache_clear()

    with patch.object(la_module, "_rate_limited_geocode", side_effect=_mock_rate_limited_geocode):
        from event_agent.agents.location_agent import LocationAgent
        agent = LocationAgent()
        yield agent

    la_module._geocode.cache_clear()
    la_module._zip_centroid.cache_clear()


def test_virtual_event_passes_through(location_agent):
    result = location_agent.process(_make_event(is_virtual=True))
    assert result is not None
    assert result["distance_miles"] is None


def test_nearby_event_passes_filter(location_agent):
    result = location_agent.process(_make_event(
        location_text="New York Convention Center, New York, NY",
        is_virtual=False,
    ))
    assert result is not None
    assert result["distance_miles"] is not None
    assert result["distance_miles"] < 120


def test_far_event_filtered_out(location_agent):
    result = location_agent.process(_make_event(
        location_text="Los Angeles Convention Center, Los Angeles, CA",
        is_virtual=False,
    ))
    assert result is None


def test_online_location_text_passes(location_agent):
    result = location_agent.process(_make_event(location_text="Online"))
    assert result is not None


def test_no_location_passes(location_agent):
    result = location_agent.process(_make_event(location_text=None))
    assert result is not None
