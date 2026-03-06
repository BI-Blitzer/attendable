"""Integration test for AgentCrew pipeline using mocked dependencies."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from event_agent.scrapers.base import RawEvent


SAMPLE_RAW_EVENTS = [
    RawEvent(
        source="eventbrite",
        source_id="eb-001",
        title="NJ BI Summit 2026",
        url="https://www.eventbrite.com/e/nj-bi-summit-001",
        description="Business intelligence summit in NJ.",
        start_datetime="2026-09-15T09:00:00Z",
        location_text="1 Convention Blvd, Atlantic City, NJ 08401",
        is_virtual=False,
    ),
    RawEvent(
        source="luma",
        source_id="luma-002",
        title="Virtual Data Engineering Meetup",
        url="https://lu.ma/e/virtual-de-meetup",
        description="Online meetup for data engineers.",
        start_datetime="2026-10-01T18:00:00Z",
        location_text="Online",
        is_virtual=True,
    ),
    RawEvent(
        source="meetup",
        source_id="meetup-003",
        title="LA Tech Expo",
        url="https://meetup.com/events/la-tech-expo",
        description="Tech expo in Los Angeles — far from NYC.",
        start_datetime="2026-11-20T10:00:00Z",
        location_text="Los Angeles Convention Center, LA, CA",
        is_virtual=False,
    ),
]

SAMPLE_CLASSIFICATION = {
    "event_type": "physical",
    "normalized_start": "2026-09-15T09:00:00+00:00",
    "normalized_end": None,
    "timezone": "America/New_York",
    "venue_name": "Atlantic City Convention Center",
    "address": "1 Convention Blvd",
    "city": "Atlantic City",
    "state": "NJ",
    "zip_code": "08401",
    "country": "US",
    "organizer": {"name": "NJ Tech Events", "website": None, "linkedin_url": None},
    "sponsors": [],
    "speakers": [],
    "industry_tags": ["Business Intelligence"],
    "technology_tags": ["Power BI", "Tableau"],
    "cost_type": "paid",
    "cost_amount": 299.0,
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
async def test_crew_pipeline_filters_and_classifies():
    """
    End-to-end pipeline test:
    - DiscoveryAgent returns 3 raw events
    - LocationAgent filters out the LA event (> 120 miles)
    - ClassifierAgent classifies the remaining 2
    - Repository.upsert_event called twice
    """
    from event_agent.config.settings import get_settings
    settings = get_settings()

    mock_repo = AsyncMock()
    mock_repo.upsert_event = AsyncMock(return_value=MagicMock(id="fake-uuid"))
    # All events are new (not yet classified in the DB)
    mock_repo.get_classified_source_ids = AsyncMock(return_value=set())

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_factory = MagicMock(return_value=mock_session)

    with (
        patch("event_agent.agents.crew.DiscoveryAgent") as MockDiscovery,
        patch("event_agent.agents.crew.LocationAgent") as MockLocation,
        patch("event_agent.agents.crew.ClassifierAgent") as MockClassifier,
        patch("event_agent.agents.crew.get_session_factory", return_value=mock_factory),
        patch("event_agent.agents.crew.EventRepository", return_value=mock_repo),
    ):
        # DiscoveryAgent returns all 3 events
        mock_discovery_inst = AsyncMock()
        mock_discovery_inst.fetch_all = AsyncMock(return_value=SAMPLE_RAW_EVENTS)
        MockDiscovery.return_value = mock_discovery_inst

        # LocationAgent: pass NJ and virtual events, filter out LA
        def location_side_effect(raw_event):
            if raw_event.source_id == "meetup-003":
                return None  # filtered out
            if raw_event.is_virtual:
                return {"latitude": None, "longitude": None, "distance_miles": None}
            return {"latitude": 39.36, "longitude": -74.43, "distance_miles": 45.2}

        mock_location_inst = MagicMock()
        mock_location_inst.process = location_side_effect
        MockLocation.return_value = mock_location_inst

        # ClassifierAgent returns a fixed classification
        mock_classifier_inst = AsyncMock()
        mock_classifier_inst.classify = AsyncMock(
            side_effect=lambda raw: {
                **{
                    "source": raw.source,
                    "source_id": raw.source_id,
                    "title": raw.title,
                    "description": raw.description,
                    "event_url": raw.url,
                    "raw_data": raw.raw_data,
                    "event_type": "virtual" if raw.is_virtual else "physical",
                    "start_datetime": None,
                    "end_datetime": None,
                    "timezone": None,
                    "venue_name": None,
                    "address": None,
                    "city": None,
                    "state": None,
                    "zip_code": None,
                    "country": None,
                    "registration_url": None,
                    "cost_type": "free",
                    "cost_amount": None,
                    "organizer_data": None,
                    "sponsors_data": [],
                    "speakers_data": [],
                    "industry_tags": ["Business Intelligence"],
                    "technology_tags": [],
                }
            }
        )
        MockClassifier.return_value = mock_classifier_inst

        from event_agent.agents.crew import AgentCrew
        crew = AgentCrew(settings)
        summary = await crew.run()

    assert summary["discovered"] == 3
    assert summary["location_passed"] == 2   # LA filtered out
    assert summary["newly_classified"] == 2
    assert summary["already_classified"] == 0
    assert summary["inserted_or_updated"] == 2
    assert summary["errors"] == 0


@pytest.mark.asyncio
async def test_crew_source_filter():
    """--source flag restricts DiscoveryAgent to one scraper."""
    from event_agent.config.settings import get_settings
    settings = get_settings()

    mock_repo = AsyncMock()
    mock_repo.get_classified_source_ids = AsyncMock(return_value=set())

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_factory = MagicMock(return_value=mock_session)

    with patch("event_agent.agents.crew.DiscoveryAgent") as MockDiscovery:
        mock_inst = AsyncMock()
        mock_inst.fetch_all = AsyncMock(return_value=[])
        MockDiscovery.return_value = mock_inst

        with (
            patch("event_agent.agents.crew.LocationAgent"),
            patch("event_agent.agents.crew.ClassifierAgent"),
            patch("event_agent.agents.crew.get_session_factory", return_value=mock_factory),
            patch("event_agent.agents.crew.EventRepository", return_value=mock_repo),
        ):
            from event_agent.agents.crew import AgentCrew
            crew = AgentCrew(settings)
            await crew.run(source_filter="eventbrite")

        MockDiscovery.assert_called_once_with(source_filter="eventbrite")
