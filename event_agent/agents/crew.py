"""AgentCrew — orchestrates the full pipeline: discover → locate → classify → store."""
from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Callable

from event_agent.agents.classifier_agent import ClassifierAgent
from event_agent.agents.discovery_agent import DiscoveryAgent
from event_agent.agents.location_agent import LocationAgent
from event_agent.config.settings import Settings
from event_agent.db.engine import get_session_factory
from event_agent.db.repository import EventRepository
from event_agent.scrapers.base import RawEvent

logger = logging.getLogger(__name__)

# Rate-limit parameters for classifier batching.
# Free-tier Anthropic: 8,000 output tokens/minute.
# At ~300 tokens/event, 3 events per 5-second window ≈ 3,600 tokens/min — safe.
_BATCH_SIZE = 3
_BATCH_DELAY_SECONDS = 5


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


class AgentCrew:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._location_agent = LocationAgent()
        self._classifier_agent = ClassifierAgent()

    async def run(
        self,
        source_filter: str | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict:
        """
        Run the full pipeline:
          1. Discover raw events
          2. Filter by location
          3. Classify with Claude
          4. Upsert to database

        Returns a summary dict.
        """
        def _progress(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        logger.info("AgentCrew: starting pipeline (source_filter=%s)", source_filter)

        # Step 1: Discovery — sequential (with callback) so UI shows per-scraper status
        discovery = DiscoveryAgent(source_filter=source_filter)
        raw_events = await discovery.fetch_all(progress_callback=_progress)
        logger.info("AgentCrew: discovered %d raw events", len(raw_events))

        # Step 2: Location filter
        _progress(f"Filtering {len(raw_events)} events by location…")
        located: list[tuple[RawEvent, dict]] = []
        for raw_event in raw_events:
            geo_data = self._location_agent.process(raw_event)
            if geo_data is not None:
                located.append((raw_event, geo_data))

        logger.info("AgentCrew: %d events passed location filter", len(located))

        # Step 3: Skip events already classified in the DB
        _progress(f"Checking {len(located)} events against database…")
        factory = get_session_factory()
        async with factory() as check_session:
            repo = EventRepository(check_session)
            already_classified = await repo.get_classified_source_ids(
                [(e.source, e.source_id) for e, _ in located]
            )

        to_classify = [(e, g) for e, g in located if (e.source, e.source_id) not in already_classified]
        to_update_geo = [(e, g) for e, g in located if (e.source, e.source_id) in already_classified]
        logger.info(
            "AgentCrew: %d new events to classify, %d already classified (geo update only)",
            len(to_classify), len(to_update_geo),
        )

        # Step 4: Classify new events in rate-limited batches
        async def classify_one(raw_event: RawEvent, geo_data: dict) -> dict | None:
            try:
                event_data = await self._classifier_agent.classify(raw_event)
                event_data.update(geo_data)
                return event_data
            except Exception as exc:
                logger.error("Classification failed for %r: %s", raw_event.title, exc)
                return None

        classified_results: list[dict | None] = []
        batches = list(_chunks(to_classify, _BATCH_SIZE))
        for i, batch in enumerate(batches):
            _progress(f"Classifying batch {i + 1} / {len(batches)}…")
            results = await asyncio.gather(*[classify_one(raw, geo) for raw, geo in batch])
            classified_results.extend(results)
            if i < len(batches) - 1:
                logger.info(
                    "Classifier batch %d/%d done — waiting %ds before next batch",
                    i + 1, len(batches), _BATCH_DELAY_SECONDS,
                )
                await asyncio.sleep(_BATCH_DELAY_SECONDS)

        newly_classified = [r for r in classified_results if r is not None]
        logger.info("AgentCrew: %d new events classified", len(newly_classified))

        # Step 5: Upsert — new (fully classified) + known (geo update only)
        total_to_save = len(newly_classified) + len(to_update_geo)
        _progress(f"Saving {total_to_save} events to database…")
        inserted = 0
        errors = 0
        async with factory() as session:
            repo = EventRepository(session)

            for event_data in newly_classified:
                try:
                    await repo.upsert_event(event_data)
                    inserted += 1
                except Exception as exc:
                    logger.error("Upsert failed for %r: %s", event_data.get("title"), exc)
                    errors += 1

            for raw_event, geo_data in to_update_geo:
                try:
                    # Only refresh geo fields — everything else is already correct in DB.
                    # Passing raw string datetimes from scrapers would cause type errors.
                    await repo.upsert_event({
                        "source": raw_event.source,
                        "source_id": raw_event.source_id,
                        **geo_data,
                    })
                    inserted += 1
                except Exception as exc:
                    logger.error("Geo-update failed for %r: %s", raw_event.title, exc)
                    errors += 1

        summary = {
            "discovered": len(raw_events),
            "location_passed": len(located),
            "newly_classified": len(newly_classified),
            "already_classified": len(to_update_geo),
            "inserted_or_updated": inserted,
            "errors": errors,
            "source_counts": dict(Counter(e.source for e in raw_events)),
        }
        logger.info("AgentCrew: run complete — %s", summary)
        return summary
