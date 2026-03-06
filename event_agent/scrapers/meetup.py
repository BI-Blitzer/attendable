"""Meetup.com scraper using Playwright (no API key required).

First-time setup: uv run playwright install chromium
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from event_agent.config.settings import get_settings
from event_agent.scrapers.base import BaseScraper, RawEvent

logger = logging.getLogger(__name__)


def _distance_bucket(miles: int) -> str:
    """Map a radius in miles to Meetup's distance parameter."""
    if miles <= 10:
        return "tenMiles"
    if miles <= 25:
        return "twentyFiveMiles"
    if miles <= 50:
        return "fiftyMiles"
    return "hundredMiles"


class MeetupScraper(BaseScraper):
    source_name = "meetup"

    def __init__(self):
        settings = get_settings()
        self._center_zip = settings.center_zip
        self._radius_miles = settings.radius_miles

    async def fetch(self, keywords: list[str]) -> list[RawEvent]:
        try:
            from playwright.async_api import async_playwright  # noqa: PLC0415
        except ImportError:
            logger.warning(
                "Meetup: playwright not installed — skipping. "
                "Run: uv run playwright install chromium"
            )
            return []

        results: list[RawEvent] = []
        seen_ids: set[str] = set()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                ctx = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/121.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                )
                page = await ctx.new_page()

                # Speed up by blocking images and fonts
                await page.route(
                    "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,eot}",
                    lambda r: r.abort(),
                )

                for keyword in keywords:
                    evts = await self._fetch_keyword(page, keyword, seen_ids)
                    results.extend(evts)

                await browser.close()
        except Exception as exc:
            logger.error("Meetup: browser session failed: %s", exc)

        logger.info("Meetup: fetched %d raw events", len(results))
        return results

    async def _fetch_keyword(
        self, page, keyword: str, seen_ids: set
    ) -> list[RawEvent]:
        dist = _distance_bucket(self._radius_miles)
        url = (
            "https://www.meetup.com/find/"
            f"?keywords={quote_plus(keyword)}"
            "&source=EVENTS"
            "&eventType=inPerson"
            f"&distance={dist}"
            f"&location={self._center_zip}"
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            # Give React/Next.js time to hydrate the event list
            await page.wait_for_timeout(2_500)
        except Exception as exc:
            logger.warning("Meetup: page load failed for %r: %s", keyword, exc)
            return []

        # Extract event data entirely inside the browser context so we can
        # traverse the live DOM without round-tripping for each element.
        raw_items: list[dict] = await page.evaluate(
            """() => {
            const results = [];
            const seen = new Set();

            // Collect every link that looks like a Meetup event URL.
            const eventLinks = Array.from(document.querySelectorAll('a[href]')).filter(a =>
                /meetup\\.com\\/[^/]+\\/events\\/\\d+/.test(a.href)
            );

            for (const link of eventLinks) {
                const m = link.href.match(/\\/events\\/(\\d+)/);
                if (!m) continue;
                const id = m[1];
                if (seen.has(id)) continue;
                seen.add(id);

                // In Meetup's current UI the <a> element IS the event card
                // (class "group inline size-full cursor-pointer...").
                // Do NOT walk up the DOM — walking up lands on a shared ancestor
                // where querySelector('h2') returns the same first heading for
                // every card.
                const card = link;

                // Title: the link text has format "{title}{Weekday}, {date} by {group}".
                // Split at the first weekday abbreviation to isolate the title.
                const fullText = (link.textContent || '').replace(/\\s+/g, ' ').trim();
                let title = '';
                const weekdayIdx = fullText.search(/\\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun),\\s/);
                if (weekdayIdx > 0) {
                    title = fullText.substring(0, weekdayIdx).trim();
                } else {
                    // Fallback: try a heading element inside the card
                    const headingEl = card.querySelector('h2,h3,h4,h5');
                    title = headingEl ? headingEl.textContent.trim() : fullText.substring(0, 120).trim();
                }
                if (!title || title.length < 4) continue;

                // Date: look for <time datetime="..."> inside the card.
                const timeEl = card.querySelector('time[datetime]');
                const startDt = timeEl ? timeEl.getAttribute('datetime') : null;

                // Location: scan child spans/paras for location-like text.
                // Skip elements that look like the title or a time string.
                let locationText = null;
                for (const el of card.querySelectorAll('span,p')) {
                    const t = el.textContent.trim();
                    if (!t || t.length < 3 || t.length > 100) continue;
                    if (t === title) continue;
                    if (/\\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun),/.test(t)) continue;
                    if (/\\b(AM|PM|EDT|EST|CDT|CST|PDT|PST|UTC)\\b/.test(t)) continue;
                    if (t.includes(',') || /\\s[A-Z]{2}(\\s|$)/.test(t)) {
                        locationText = t;
                        break;
                    }
                }

                // Organizer: "by {name}" at end of full link text.
                let groupName = null;
                const byMatch = fullText.match(/\\bby\\s+(.{3,80})$/);
                if (byMatch) groupName = byMatch[1].trim();

                results.push({ id, title, url: link.href, startDt, locationText, groupName });
            }
            return results;
        }"""
        )

        logger.debug(
            "Meetup: found %d event links for %r", len(raw_items), keyword
        )

        if not raw_items:
            logger.info(
                "Meetup: JS extraction returned 0 items for %r — trying JSON-LD fallback",
                keyword,
            )
            return await self._fetch_jsonld_fallback(page, seen_ids)

        events: list[RawEvent] = []
        for item in raw_items[:30]:
            eid = str(item["id"])
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            city, state = _parse_city_state(item.get("locationText") or "")

            organizer_data = None
            if item.get("groupName"):
                organizer_data = {"name": item["groupName"]}

            events.append(
                RawEvent(
                    source=self.source_name,
                    source_id=eid,
                    title=item["title"],
                    description=None,
                    start_datetime=item.get("startDt"),
                    end_datetime=None,
                    location_text=item.get("locationText") or None,
                    is_virtual=False,
                    url=item["url"],
                    city=city,
                    state=state,
                    raw_data=item,
                )
            )

        return events

    async def _fetch_jsonld_fallback(self, page, seen_ids: set) -> list[RawEvent]:
        """
        Fallback when JS card extraction returns 0 items.
        Gets event URLs from the current page via Playwright, then fetches each
        page with httpx and parses schema.org JSON-LD Event data.
        """
        urls: list[str] = await page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href*="/events/"]'))
                .map(a => a.href)
                .filter(h => /meetup\\.com\\/[^/]+\\/events\\/\\d+/.test(h))
                .slice(0, 10)"""
        )
        logger.debug("Meetup JSON-LD fallback: found %d event URLs", len(urls))
        if not urls:
            return []

        sem = asyncio.Semaphore(5)

        async def _fetch_one(url: str) -> RawEvent | None:
            m = re.search(r"/events/(\d+)", url)
            if not m:
                return None
            eid = m.group(1)
            if eid in seen_ids:
                return None

            async with sem:
                try:
                    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                        resp = await client.get(
                            url,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; event-agent/1.0)"},
                        )
                        if resp.status_code != 200:
                            return None
                        html = resp.text
                except Exception as exc:
                    logger.debug("Meetup JSON-LD: fetch failed for %s: %s", url, exc)
                    return None

            soup = BeautifulSoup(html, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = _json.loads(script.string or "")
                except Exception:
                    continue
                if not isinstance(data, dict) or data.get("@type") != "Event":
                    continue
                name = data.get("name", "")
                if not name or len(name) < 4:
                    continue

                start_date = data.get("startDate")
                end_date = data.get("endDate")
                description = data.get("description")
                loc = data.get("location") or {}
                addr = loc.get("address") or {}
                city = addr.get("addressLocality")
                state = addr.get("addressRegion")
                location_parts = [v for v in [loc.get("name"), city, state] if v]
                location_text = ", ".join(location_parts) if location_parts else None

                seen_ids.add(eid)
                return RawEvent(
                    source=self.source_name,
                    source_id=eid,
                    title=name,
                    description=description,
                    start_datetime=start_date,
                    end_datetime=end_date,
                    location_text=location_text,
                    is_virtual=False,
                    url=url,
                    city=city,
                    state=state,
                    raw_data=data,
                )
            return None

        results = await asyncio.gather(*[_fetch_one(u) for u in urls])
        events = [r for r in results if r is not None]
        logger.info("Meetup JSON-LD fallback: extracted %d events", len(events))
        return events


def _parse_city_state(location_text: str) -> tuple[str | None, str | None]:
    """
    Best-effort parse of "Venue, 123 Main St, City, ST 00000" → (city, state).
    Returns (None, None) on failure.
    """
    if not location_text:
        return None, None
    parts = [p.strip() for p in location_text.split(",") if p.strip()]
    if len(parts) < 2:
        return None, None
    # Last part often looks like "ST 00000" or just "ST"
    state_m = re.match(r"^([A-Z]{2})\b", parts[-1])
    if state_m:
        state = state_m.group(1)
        city = parts[-2] if len(parts) >= 2 else None
        return city, state
    return None, None
