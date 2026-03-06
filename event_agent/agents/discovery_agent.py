"""Discovery agent — orchestrates all enabled scrapers."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

from event_agent.config.settings import get_settings
from event_agent.scrapers.base import BaseScraper, RawEvent
from event_agent.scrapers.eventbrite import EventbriteScraper
from event_agent.scrapers.luma import LumaScraper
from event_agent.scrapers.meetup import MeetupScraper
from event_agent.scrapers.web_search import WebSearchScraper

logger = logging.getLogger(__name__)

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "eventbrite": EventbriteScraper,
    "meetup": MeetupScraper,
    "luma": LumaScraper,
    "web_search": WebSearchScraper,
}


class DiscoveryAgent:
    def __init__(self, source_filter: str | None = None):
        settings = get_settings()
        enabled = settings.enabled_sources
        if source_filter:
            enabled = [s for s in enabled if s == source_filter]

        self._scrapers: list[BaseScraper] = []
        for name in enabled:
            cls = SCRAPER_REGISTRY.get(name)
            if cls:
                self._scrapers.append(cls())
            else:
                logger.warning("Unknown scraper source: %s", name)

        self._keywords = settings.search_keywords

    async def fetch_all(
        self,
        progress_callback: Callable[[str], None] | None = None,
    ) -> list[RawEvent]:
        """
        Run all enabled scrapers and return merged results.
        When a progress_callback is provided, scrapers run sequentially so the
        UI can show which source is currently being scraped.
        Without a callback (e.g. CLI), scrapers run concurrently for speed.
        """
        all_events: list[RawEvent] = []

        if progress_callback:
            for scraper in self._scrapers:
                label = scraper.source_name.replace("_", " ").title()
                progress_callback(f"Scraping {label}…")
                try:
                    events = await scraper.fetch(self._keywords)
                    all_events.extend(events)
                    logger.info("Scraper %s: %d events", scraper.source_name, len(events))
                except Exception as exc:
                    logger.error("Scraper %s failed: %s", scraper.source_name, exc)
        else:
            tasks = [scraper.fetch(self._keywords) for scraper in self._scrapers]
            results_per_scraper = await asyncio.gather(*tasks, return_exceptions=True)
            for scraper, result in zip(self._scrapers, results_per_scraper):
                if isinstance(result, Exception):
                    logger.error("Scraper %s failed: %s", scraper.source_name, result)
                else:
                    all_events.extend(result)

        logger.info("Discovery: total %d raw events from %d scrapers", len(all_events), len(self._scrapers))
        return all_events
