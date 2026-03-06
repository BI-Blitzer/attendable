"""Base scraper interface and shared data types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawEvent:
    source: str
    source_id: str
    title: str
    url: str
    description: str | None = None
    start_datetime: str | None = None   # raw string — ClassifierAgent normalises
    end_datetime: str | None = None
    location_text: str | None = None    # raw location string
    is_virtual: bool | None = None
    city: str | None = None             # pre-parsed by scraper when available
    state: str | None = None
    raw_data: dict = field(default_factory=dict)


class BaseScraper(ABC):
    source_name: str

    @abstractmethod
    async def fetch(self, keywords: list[str]) -> list[RawEvent]:
        """Fetch raw events matching the given keywords."""
