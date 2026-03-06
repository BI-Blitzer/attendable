"""Lu.ma scraper — uses api2.luma.com (no auth required, no Playwright needed)."""
from __future__ import annotations

import logging

import httpx
from geopy.distance import geodesic
from tenacity import retry, stop_after_attempt, wait_exponential

from event_agent.config.settings import get_settings
from event_agent.scrapers.base import BaseScraper, RawEvent

logger = logging.getLogger(__name__)

API_BASE = "https://api2.luma.com"
LUMA_WEB_BASE = "https://lu.ma"

# Tech / BI category IDs on Luma
RELEVANT_CATEGORIES = ["cat-tech"]

# Bootstrap page is keyed to a place; NYC is a stable well-known ID
_BOOTSTRAP_ANCHOR = "discplace-Izx1rQVSh8njYpP"


class LumaScraper(BaseScraper):
    source_name = "luma"

    def __init__(self):
        settings = get_settings()
        self._center = (40.7128, -74.0060)  # default NYC; overridden by settings center_lat/lon
        self._radius_miles = settings.radius_miles

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, client: httpx.AsyncClient, path: str, params: dict) -> dict:
        r = await client.get(
            f"{API_BASE}{path}",
            params=params,
            headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Find nearby Luma "places" (cities)
    # ------------------------------------------------------------------

    async def _nearby_place_ids(self, client: httpx.AsyncClient) -> list[str]:
        """Return Luma place API IDs whose coordinates are within radius_miles of center."""
        data = await self._get(
            client, "/discover/bootstrap-page",
            {"featured_place_api_id": _BOOTSTRAP_ANCHOR},
        )
        place_ids = []
        for entry in data.get("places", []):
            place = entry.get("place", {})
            coord = place.get("coordinate", {})
            lat, lon = coord.get("latitude"), coord.get("longitude")
            if lat and lon:
                dist = geodesic(self._center, (lat, lon)).miles
                if dist <= self._radius_miles:
                    place_ids.append(place["api_id"])
                    logger.debug("Luma place %s (%s) is %.0f mi away", place["api_id"], place.get("slug"), dist)
        return place_ids

    # ------------------------------------------------------------------
    # Fetch events for one place + category
    # ------------------------------------------------------------------

    async def _fetch_place_events(
        self,
        client: httpx.AsyncClient,
        place_id: str,
        category_id: str,
    ) -> list[dict]:
        entries: list[dict] = []
        cursor = None
        while True:
            params: dict = {
                "discover_place_api_id": place_id,
                "category_api_id": category_id,
                "pagination_limit": 50,
            }
            if cursor:
                params["pagination_cursor"] = cursor

            try:
                data = await self._get(client, "/discover/get-paginated-events", params)
            except Exception as exc:
                logger.warning("Luma paginated-events error (%s, %s): %s", place_id, category_id, exc)
                break

            entries.extend(data.get("entries", []))

            if data.get("has_more") and data.get("next_cursor"):
                cursor = data["next_cursor"]
            else:
                break

        return entries

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch(self, keywords: list[str]) -> list[RawEvent]:
        # keywords are ignored — we use category + location filtering instead
        results: list[RawEvent] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient() as client:
            place_ids = await self._nearby_place_ids(client)
            if not place_ids:
                logger.warning("Luma: no nearby places found within %d miles", self._radius_miles)
                return []

            logger.info("Luma: found %d nearby places: %s", len(place_ids), place_ids)

            for place_id in place_ids:
                for category_id in RELEVANT_CATEGORIES:
                    entries = await self._fetch_place_events(client, place_id, category_id)
                    for entry in entries:
                        event = entry.get("event", {})
                        eid = event.get("api_id", "")
                        if not eid or eid in seen_ids:
                            continue
                        seen_ids.add(eid)
                        results.append(self._parse(event, entry))

        logger.info("Luma: fetched %d raw events", len(results))
        return results

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse(self, event: dict, entry: dict) -> RawEvent:
        geo = event.get("geo_address_info") or {}
        location_text = geo.get("full_address") or geo.get("description") or geo.get("city_state")
        is_online = event.get("location_type") == "online"

        # Parse city/state directly from structured field (e.g. "Newark, NJ")
        city = state = None
        city_state = geo.get("city_state", "") or ""
        if city_state and "," in city_state:
            parts = city_state.split(",", 1)
            city, state = parts[0].strip(), parts[1].strip()

        return RawEvent(
            source=self.source_name,
            source_id=event["api_id"],
            title=event.get("name", ""),
            description=event.get("description_short") or event.get("description"),
            start_datetime=event.get("start_at"),
            end_datetime=event.get("end_at"),
            location_text="Online" if is_online else location_text,
            is_virtual=is_online,
            city=None if is_online else city,
            state=None if is_online else state,
            url=f"{LUMA_WEB_BASE}/e/{event.get('url', event['api_id'])}",
            raw_data=entry,
        )
