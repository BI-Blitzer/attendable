"""Classifier agent — uses Claude to extract structured metadata from raw events."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from event_agent.agents.base import BaseAgent
from event_agent.scrapers.base import RawEvent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert event data analyst. You extract structured metadata from raw event records.
Always return valid JSON. Be concise and accurate. If a field cannot be determined, use null."""

EXTRACTION_PROMPT = """Extract structured event metadata from the following raw event data.

Raw event:
{raw_json}

Return a JSON object with exactly these fields:
{{
  "normalized_start": "<ISO 8601 datetime or null>",
  "normalized_end": "<ISO 8601 datetime or null>",
  "event_type": "virtual" | "physical" | "hybrid",
  "timezone": "<IANA timezone string or null>",
  "venue_name": "<string or null>",
  "address": "<street address or null>",
  "city": "<string or null>",
  "state": "<string or null>",
  "zip_code": "<string or null>",
  "country": "<string or null>",
  "organizer": {{"name": "<string>", "website": "<url or null>", "linkedin_url": "<url or null>"}} | null,
  "sponsors": [{{"name": "<string>", "website": "<url or null>", "linkedin_url": "<url or null>"}}],
  "speakers": [{{"name": "<string>", "title": "<string or null>", "company": "<string or null>", "linkedin_url": "<url or null>", "role": "<string or null>"}}],
  "industry_tags": ["<tag>"],
  "technology_tags": ["<tag>"],
  "cost_type": "free" | "paid",
  "cost_amount": <number or null>
}}

Return only the JSON object, no explanation."""


class ClassifierAgent(BaseAgent):
    def __init__(self):
        super().__init__(SYSTEM_PROMPT)

    async def classify(self, raw_event: RawEvent) -> dict:
        """
        Send the raw event to Claude and return the extracted classification dict.
        Falls back to empty defaults on failure.
        """
        # Build a clean dict to send — avoid sending huge raw_data blobs
        event_dict = {
            "title": raw_event.title,
            "description": raw_event.description,
            "start_datetime": raw_event.start_datetime,
            "end_datetime": raw_event.end_datetime,
            "location_text": raw_event.location_text,
            "is_virtual": raw_event.is_virtual,
            "url": raw_event.url,
            "source": raw_event.source,
        }

        prompt = EXTRACTION_PROMPT.format(raw_json=json.dumps(event_dict, indent=2))

        try:
            text = await self.run(prompt, max_tokens=1024)
            # Strip markdown fences
            text = text.strip()
            if text.startswith("```"):
                parts = text.split("```")
                text = parts[1] if len(parts) > 1 else text
                if text.startswith("json"):
                    text = text[4:]
            classification = json.loads(text)
        except Exception as exc:
            logger.error("Classifier failed for event %r: %s", raw_event.title, exc)
            classification = {}

        return self._to_event_data(raw_event, classification)

    def _to_event_data(self, raw_event: RawEvent, cls: dict) -> dict:
        """Merge classifier output with the raw event into a flat event dict."""
        # Parse datetimes
        start_dt = self._parse_dt(cls.get("normalized_start") or raw_event.start_datetime)
        end_dt = self._parse_dt(cls.get("normalized_end") or raw_event.end_datetime)

        # Determine event_type
        event_type = cls.get("event_type")
        if not event_type:
            if raw_event.is_virtual:
                event_type = "virtual"
            else:
                event_type = "physical"

        cost_amount = cls.get("cost_amount")
        if cost_amount is not None:
            try:
                cost_amount = float(cost_amount)
            except (TypeError, ValueError):
                cost_amount = None

        return {
            "source": raw_event.source,
            "source_id": raw_event.source_id,
            "title": raw_event.title,
            "description": raw_event.description,
            "event_type": event_type,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "timezone": cls.get("timezone"),
            "venue_name": cls.get("venue_name"),
            "address": cls.get("address"),
            "city": cls.get("city") or raw_event.city,
            "state": cls.get("state") or raw_event.state,
            "zip_code": cls.get("zip_code"),
            "country": cls.get("country"),
            "registration_url": None,
            "event_url": raw_event.url,
            "cost_type": cls.get("cost_type", "free"),
            "cost_amount": cost_amount,
            "organizer_data": cls.get("organizer"),
            "sponsors_data": cls.get("sponsors", []),
            "speakers_data": cls.get("speakers", []),
            "industry_tags": cls.get("industry_tags", []),
            "technology_tags": cls.get("technology_tags", []),
            "raw_data": raw_event.raw_data,
        }

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        from dateutil import parser as dtparser
        try:
            return dtparser.parse(value)
        except Exception:
            return None
