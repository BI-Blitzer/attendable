"""Location agent — geocodes events and filters by radius."""
from __future__ import annotations

import logging
from functools import lru_cache

from geopy.distance import geodesic
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

from event_agent.config.settings import get_settings
from event_agent.scrapers.base import RawEvent

logger = logging.getLogger(__name__)

_geolocator = Nominatim(user_agent="event-agent/1.0", timeout=10)

# Nominatim ToS: max 1 request/second. RateLimiter enforces the delay between
# actual network calls; lru_cache ensures cached results skip the limiter entirely.
_rate_limited_geocode = RateLimiter(
    _geolocator.geocode,
    min_delay_seconds=1.1,
    error_wait_seconds=5.0,
    max_retries=2,
    swallow_exceptions=True,
)


@lru_cache(maxsize=512)
def _geocode(location_text: str) -> tuple[float, float] | None:
    try:
        loc = _rate_limited_geocode(location_text)
        if loc:
            return loc.latitude, loc.longitude
    except Exception as exc:
        logger.debug("Geocode failed for %r: %s", location_text, exc)
    return None


@lru_cache(maxsize=4)
def _zip_centroid(zip_code: str) -> tuple[float, float] | None:
    return _geocode(f"{zip_code}, USA")


class LocationAgent:
    def __init__(self):
        settings = get_settings()
        self._center_zip = settings.center_zip
        self._radius_miles = settings.radius_miles
        if settings.center_lat is not None and settings.center_lon is not None:
            self._center: tuple[float, float] | None = (settings.center_lat, settings.center_lon)
        else:
            self._center = _zip_centroid(self._center_zip)

    def process(self, raw_event: RawEvent) -> dict | None:
        """
        Returns a dict with geocoding fields to merge into the event record,
        or None if the event is out of range (and not virtual).
        """
        if raw_event.is_virtual:
            return {"latitude": None, "longitude": None, "distance_miles": None}

        if not raw_event.location_text or raw_event.location_text.lower() == "online":
            return {"latitude": None, "longitude": None, "distance_miles": None}

        coords = _geocode(raw_event.location_text)
        if coords is None:
            logger.debug("Could not geocode %r — keeping event", raw_event.location_text)
            return {"latitude": None, "longitude": None, "distance_miles": None}

        if self._center is None:
            logger.warning("Center ZIP %s could not be geocoded", self._center_zip)
            return {"latitude": coords[0], "longitude": coords[1], "distance_miles": None}

        distance = geodesic(self._center, coords).miles
        if distance > self._radius_miles:
            logger.debug(
                "Event %r is %.1f miles away (limit %d) — filtered out",
                raw_event.title, distance, self._radius_miles,
            )
            return None

        return {
            "latitude": coords[0],
            "longitude": coords[1],
            "distance_miles": round(distance, 2),
        }
