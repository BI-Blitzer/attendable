"""AI-guided web search scraper — Brave Search → SerpAPI → DuckDuckGo fallback."""
from __future__ import annotations

import hashlib
import logging
from datetime import date

import httpx
import litellm
from tenacity import retry, stop_after_attempt, wait_exponential

from event_agent.agents.base import _llm_kwargs
from event_agent.config.settings import get_settings
from event_agent.scrapers.base import BaseScraper, RawEvent

logger = logging.getLogger(__name__)

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def _search_years() -> list[str]:
    """Return [current_year] normally; add next year from October onwards."""
    today = date.today()
    years = [str(today.year)]
    if today.month >= 10:
        years.append(str(today.year + 1))
    return years
SERPAPI_URL = "https://serpapi.com/search"
DDG_URL = "https://html.duckduckgo.com/html/"


class WebSearchScraper(BaseScraper):
    source_name = "web_search"

    def __init__(self):
        settings = get_settings()
        self._brave_key = settings.brave_api_key
        self._serp_key = settings.serp_api_key
        self._searxng_url = settings.searxng_url
        self._llm_model = settings.llm_model
        self._center_zip = settings.center_zip
        self._radius_miles = settings.radius_miles
        self._vendor_virtual_keywords = settings.vendor_virtual_keywords
        self._user_keywords = settings.user_keywords

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _search_brave(self, http: httpx.AsyncClient, query: str) -> list[dict]:
        response = await http.get(
            BRAVE_SEARCH_URL,
            params={"q": query, "count": 10, "country": "us"},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self._brave_key,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {"title": r.get("title", ""), "link": r.get("url", ""), "snippet": r.get("description", "")}
            for r in data.get("web", {}).get("results", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _search_serpapi(self, http: httpx.AsyncClient, query: str) -> list[dict]:
        response = await http.get(
            SERPAPI_URL,
            params={"q": query, "api_key": self._serp_key, "engine": "google", "num": 10},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("organic_results", [])

    async def _search_searxng(self, http: httpx.AsyncClient, query: str) -> list[dict]:
        try:
            response = await http.get(
                self._searxng_url,
                params={"q": query, "format": "json"},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return [
                {"title": r.get("title", ""), "link": r.get("url", ""), "snippet": r.get("content", "")}
                for r in data.get("results", [])
            ][:10]
        except Exception as exc:
            logger.debug("SearXNG search error: %s", exc)
            return []

    async def _search_ddg(self, http: httpx.AsyncClient, query: str) -> list[dict]:
        try:
            response = await http.post(
                DDG_URL,
                data={"q": query, "b": "", "kl": "us-en"},
                headers={"User-Agent": "Mozilla/5.0 (compatible; event-agent/1.0)"},
                timeout=30,
                follow_redirects=True,
            )
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            for result in soup.select(".result"):
                a = result.select_one(".result__a")
                snippet = result.select_one(".result__snippet")
                if a:
                    results.append({
                        "title": a.get_text(strip=True),
                        "link": a.get("href", ""),
                        "snippet": snippet.get_text(strip=True) if snippet else "",
                    })
            return results[:10]
        except Exception as exc:
            logger.debug("DuckDuckGo search error: %s", exc)
            return []

    async def _search(self, http: httpx.AsyncClient, query: str) -> list[dict]:
        if self._brave_key:
            try:
                results = await self._search_brave(http, query)
                logger.info("Brave Search: %d results for %r", len(results), query)
                return results
            except Exception as exc:
                logger.warning("Brave Search failed, falling back: %s", exc)
        if self._serp_key:
            try:
                results = await self._search_serpapi(http, query)
                logger.info("SerpAPI: %d results for %r", len(results), query)
                return results
            except Exception as exc:
                logger.warning("SerpAPI failed, falling back: %s", exc)
        if self._searxng_url:
            results = await self._search_searxng(http, query)
            if results:
                logger.info("SearXNG: %d results for %r", len(results), query)
                return results
        results = await self._search_ddg(http, query)
        logger.info("DuckDuckGo: %d results for %r", len(results), query)
        return results

    async def _extract_events_from_results(
        self, results: list[dict], keyword: str, virtual_only: bool = False
    ) -> list[RawEvent]:
        """Use Claude to identify which search results are tech/BI events and extract metadata."""
        if not results:
            return []

        results_text = "\n".join(
            f"{i+1}. [{r.get('title','')}]({r.get('link','')})\n   {r.get('snippet','')}"
            for i, r in enumerate(results)
        )

        if virtual_only:
            prompt = f"""You are reviewing web search results to find virtual/online technology events hosted by vendors.

Search query: "{keyword}"

These are vendor-hosted webinars, online conferences, virtual summits, and digital events.
Location does not matter — all results should be treated as online/virtual events.

Search results:
{results_text}

For each result that appears to be a webinar, virtual conference, online summit, or vendor event, extract:
- title
- url (the link provided)
- description (from snippet)
- start_date (if visible, otherwise null)
- location: set to "Online" for all virtual events
- is_virtual: always true for these

Return a JSON array. Only include results that are clearly events (not blog posts, docs, or marketing pages).
If none qualify, return [].

Example: [{{"title": "...", "url": "...", "description": "...", "start_date": null, "location": "Online", "is_virtual": true}}]

Return only the JSON array, no explanation."""
        else:
            prompt = f"""You are reviewing web search results to find technology and business intelligence events.

Search query: "{keyword}"
Target area: ZIP code {self._center_zip}, within {self._radius_miles} miles

Search results:
{results_text}

For each result that appears to be a tech/BI conference, meetup, summit, or workshop, extract:
- title
- url (the link provided)
- description (from snippet)
- start_date (if visible, otherwise null)
- location (if visible, otherwise null)
- is_virtual (true/false/null)

Return a JSON array of event objects. Only include results that are clearly events. If none qualify, return [].

Example format:
[{{"title": "...", "url": "...", "description": "...", "start_date": null, "location": null, "is_virtual": null}}]

Return only the JSON array, no explanation."""

        response = await litellm.acompletion(
            model=self._llm_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            **_llm_kwargs(),
        )
        text = (response.choices[0].message.content or "").strip()

        import json
        try:
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            events_data = json.loads(text)
        except Exception as exc:
            logger.debug("Failed to parse Claude response: %s\nResponse: %s", exc, text)
            return []

        raw_events = []
        for item in events_data:
            url = item.get("url", "")
            if not url:
                continue
            source_id = hashlib.md5(url.encode()).hexdigest()[:24]
            raw_events.append(RawEvent(
                source=self.source_name,
                source_id=source_id,
                title=item.get("title", ""),
                description=item.get("description"),
                start_datetime=item.get("start_date"),
                location_text=item.get("location"),
                is_virtual=item.get("is_virtual") if not virtual_only else True,
                url=url,
                raw_data=item,
            ))
        logger.info(
            "WebSearch: extracted %d events from %d results for %r",
            len(raw_events), len(results), keyword,
        )
        return raw_events

    async def fetch(self, keywords: list[str]) -> list[RawEvent]:
        results: list[RawEvent] = []
        seen_ids: set[str] = set()

        years = _search_years()
        effective_geo = list(keywords) + list(self._user_keywords)
        async with httpx.AsyncClient() as http:
            # ── Geo-targeted: local physical/hybrid events ────────────────────
            for keyword in effective_geo:
                for year in years:
                    query = f"{keyword} {year} near {self._center_zip}"
                    search_results = await self._search(http, query)
                    events = await self._extract_events_from_results(search_results, keyword)
                    for evt in events:
                        if evt.source_id not in seen_ids:
                            seen_ids.add(evt.source_id)
                            results.append(evt)

            # ── Vendor/virtual: no geo restriction, always online ─────────────
            if self._vendor_virtual_keywords:
                logger.info(
                    "WebSearch: running %d vendor/virtual keyword searches (years: %s)",
                    len(self._vendor_virtual_keywords),
                    ", ".join(years),
                )
                for keyword in self._vendor_virtual_keywords:
                    for year in years:
                        query = f"{keyword} {year}"
                        search_results = await self._search(http, query)
                        events = await self._extract_events_from_results(
                            search_results, keyword, virtual_only=True
                        )
                        for evt in events:
                            if evt.source_id not in seen_ids:
                                seen_ids.add(evt.source_id)
                                results.append(evt)

        logger.info("WebSearch: fetched %d raw events total", len(results))
        return results
