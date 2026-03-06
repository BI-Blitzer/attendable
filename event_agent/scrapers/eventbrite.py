"""Eventbrite scraper using Playwright (no API key required).

The Eventbrite REST API v3 /events/search endpoint was deprecated in 2023.
This scraper uses Playwright to browse eventbrite.com search pages and
extracts events from the Next.js server-side rendered __NEXT_DATA__ JSON,
with a DOM-based fallback.

First-time setup: uv run playwright install chromium
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import re
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from event_agent.config.settings import get_settings
from event_agent.scrapers.base import BaseScraper, RawEvent

logger = logging.getLogger(__name__)


def _zip_to_location_slug(zip_code: str) -> str:
    """Map a US ZIP prefix to an Eventbrite city/state location slug."""
    if not zip_code or not zip_code[:3].isdigit():
        return "united-states--us"
    p = int(zip_code[:3])
    # fmt: off
    if   p <=  9:  return "ma--massachusetts"
    elif p <= 27:  return "ma--massachusetts"
    elif p <= 29:  return "ri--rhode-island"
    elif p <= 49:  return "me--maine"
    elif p <= 59:  return "vt--vermont"
    elif p <= 69:  return "ct--connecticut"
    elif p <= 89:  return "nj--new-jersey"      # 070-089
    elif p <= 119: return "ny--new-york"
    elif p <= 149: return "ny--new-york"
    elif p <= 196: return "pa--pennsylvania"
    elif p <= 199: return "de--delaware"
    elif p <= 205: return "dc--district-of-columbia"
    elif p <= 219: return "md--maryland"
    elif p <= 246: return "va--virginia"
    elif p <= 268: return "wv--west-virginia"
    elif p <= 299: return "nc--north-carolina"
    elif p <= 319: return "ga--georgia"
    elif p <= 349: return "fl--florida"
    elif p <= 369: return "al--alabama"
    elif p <= 385: return "tn--tennessee"
    elif p <= 399: return "ms--mississippi"
    elif p <= 427: return "ky--kentucky"
    elif p <= 459: return "oh--ohio"
    elif p <= 479: return "in--indiana"
    elif p <= 499: return "mi--michigan"
    elif p <= 528: return "ia--iowa"
    elif p <= 549: return "wi--wisconsin"
    elif p <= 567: return "mn--minnesota"
    elif p <= 588: return "sd--south-dakota"
    elif p <= 599: return "mt--montana"
    elif p <= 629: return "il--illinois"
    elif p <= 658: return "mo--missouri"
    elif p <= 679: return "ks--kansas"
    elif p <= 693: return "ne--nebraska"
    elif p <= 714: return "la--louisiana"
    elif p <= 729: return "ar--arkansas"
    elif p <= 749: return "ok--oklahoma"
    elif p <= 799: return "tx--texas"
    elif p <= 816: return "co--colorado"
    elif p <= 831: return "wy--wyoming"
    elif p <= 838: return "id--idaho"
    elif p <= 847: return "ut--utah"
    elif p <= 865: return "az--arizona"
    elif p <= 884: return "nm--new-mexico"
    elif p <= 898: return "nv--nevada"
    elif p <= 961: return "ca--california"
    elif p <= 979: return "or--oregon"
    elif p <= 994: return "wa--washington"
    else:          return "ak--alaska"
    # fmt: on


def _keyword_slug(keyword: str) -> str:
    """Convert a keyword to an Eventbrite URL path segment."""
    slug = keyword.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug


def _parse_city_state(location_text: str) -> tuple[str | None, str | None]:
    """Best-effort parse of location string → (city, state abbr)."""
    if not location_text:
        return None, None
    parts = [p.strip() for p in location_text.split(",") if p.strip()]
    if len(parts) < 2:
        return None, None
    state_m = re.match(r"^([A-Z]{2})\b", parts[-1])
    if state_m:
        return parts[-2], state_m.group(1)
    return None, None


# ---------------------------------------------------------------------------
# JavaScript injected into the Eventbrite search page
# ---------------------------------------------------------------------------

_EXTRACT_JS = r"""
() => {
    const results = [];

    // --- Strategy 1: extract from __NEXT_DATA__ (Next.js SSR JSON) ----------
    try {
        const nd = document.getElementById('__NEXT_DATA__');
        if (nd) {
            const data = JSON.parse(nd.textContent);
            const pp = (data.props && data.props.pageProps) || {};
            const sp = pp.serverPayload || pp;

            const eventsList =
                (sp.discover_data && sp.discover_data.events && sp.discover_data.events.results) ||
                (sp.events && sp.events.results) ||
                (Array.isArray(pp.events) ? pp.events : null) ||
                [];

            if (Array.isArray(eventsList) && eventsList.length > 0) {
                for (const evt of eventsList) {
                    const id = String(evt.id || evt.event_id || '');
                    if (!id) continue;
                    const venue = evt.primary_venue || evt.venue || {};
                    const addr  = venue.address || {};
                    const locParts = [venue.name, addr.city, addr.region].filter(Boolean);
                    results.push({
                        id,
                        title:        evt.name || evt.title || '',
                        url:          evt.url   || evt.event_url || '',
                        startDt:      evt.start_date || (evt.start && evt.start.utc) || null,
                        endDt:        evt.end_date   || (evt.end   && evt.end.utc)   || null,
                        locationText: locParts.join(', ') || null,
                        city:         addr.city   || null,
                        state:        addr.region || null,
                        isOnline:     !!(evt.is_online_event || evt.online_event),
                        description:  evt.summary || null,
                    });
                }
            }
        }
    } catch(e) {}

    if (results.length > 0) return results;

    // --- Strategy 2: extract from DOM event card links ----------------------
    const seenIds = new Set();
    const eventLinks = Array.from(document.querySelectorAll('a[href*="/e/"]'))
        .filter(a => a.href.includes('eventbrite.'));

    for (const link of eventLinks) {
        const path = link.href.split('?')[0].split('#')[0];
        const nums = path.match(/(\d+)$/);
        if (!nums || nums[1].length < 6) continue;
        const id = nums[1];
        if (seenIds.has(id)) continue;
        seenIds.add(id);

        const card = link.closest('article,[data-event-id]') || link;
        const titleEl = card.querySelector('h3,h2,[class*="title"],[class*="event-name"]');
        const title = titleEl ? titleEl.textContent.trim()
                              : link.textContent.trim().substring(0, 120);
        if (!title || title.length < 4) continue;

        const timeEl = card.querySelector('time');
        const startDt = timeEl ? (timeEl.getAttribute('datetime') || null) : null;

        const locEl = card.querySelector('[class*="location"],[class*="venue"]');
        const locationText = locEl ? locEl.textContent.trim() : null;

        results.push({
            id, title, url: link.href,
            startDt, endDt: null,
            locationText, city: null, state: null,
            isOnline: false, description: null,
        });
    }

    return results;
}
"""


class EventbriteScraper(BaseScraper):
    source_name = "eventbrite"

    def __init__(self):
        settings = get_settings()
        self._center_zip = settings.center_zip
        self._location_slug = _zip_to_location_slug(settings.center_zip)

    async def fetch(self, keywords: list[str]) -> list[RawEvent]:
        try:
            from playwright.async_api import async_playwright  # noqa: PLC0415
            from playwright_stealth import Stealth  # noqa: PLC0415
        except ImportError:
            logger.warning(
                "Eventbrite: playwright or playwright-stealth not installed — skipping. "
                "Run: uv run playwright install chromium && uv add playwright-stealth"
            )
            return []

        stealth = Stealth()
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
                await stealth.apply_stealth_async(page)
                await page.route(
                    "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,eot}",
                    lambda r: r.abort(),
                )

                for keyword in keywords:
                    evts = await self._fetch_keyword(page, keyword, seen_ids)
                    results.extend(evts)

                await browser.close()
        except Exception as exc:
            logger.error("Eventbrite: browser session failed: %s", exc)

        logger.info("Eventbrite: fetched %d raw events", len(results))
        return results

    async def _fetch_keyword(
        self, page, keyword: str, seen_ids: set
    ) -> list[RawEvent]:
        # Use the ?q= search URL — more reliable than category slug paths.
        from urllib.parse import urlencode  # noqa: PLC0415
        url = (
            f"https://www.eventbrite.com/d/{self._location_slug}/events/?"
            + urlencode({"q": keyword})
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3_000)
        except Exception as exc:
            logger.warning("Eventbrite: page load failed for %r: %s", keyword, exc)
            return []

        # Quick sanity check — detect Cloudflare challenges.
        title = await page.evaluate("() => document.title")
        if "just a moment" in title.lower() or "attention required" in title.lower():
            logger.warning("Eventbrite: Cloudflare block detected for %r", keyword)
            return []

        # Minimal JS — just return href strings (proven reliable in diagnostics).
        # All parsing logic lives in Python where it's easy to debug.
        hrefs: list[str] = await page.evaluate(
            "() => Array.from(document.querySelectorAll('a[href*=\"/e/\"]'))"
            ".filter(a => a.href.includes('eventbrite.'))"
            ".map(a => a.href)"
        )
        logger.info("Eventbrite: got %d hrefs for %r", len(hrefs), keyword)
        return await self._enrich_hrefs(hrefs, seen_ids)

    async def _enrich_hrefs(self, hrefs: list[str], seen_ids: set) -> list[RawEvent]:
        """
        Fetch individual Eventbrite event pages to extract rich JSON-LD data.
        Falls back to a slug-derived RawEvent if the page is blocked or has no JSON-LD.
        """
        _EVENT_TYPES = {"Event", "MusicEvent", "SocialEvent", "BusinessEvent", "EducationEvent"}

        # Deduplicate URLs first
        seen_urls: set[str] = set()
        unique_hrefs: list[str] = []
        for href in hrefs:
            clean = href.split("?")[0].split("#")[0].rstrip("/")
            if clean not in seen_urls:
                seen_urls.add(clean)
                unique_hrefs.append(clean)
            if len(unique_hrefs) >= 50:
                break

        sem = asyncio.Semaphore(5)

        async def _fetch_one(clean_url: str) -> RawEvent | None:
            m = re.search(r"-(\d{6,})$", clean_url)
            if not m:
                return None
            eid = m.group(1)
            if eid in seen_ids:
                return None

            slug = clean_url.rsplit("/", 1)[-1]
            slug = re.sub(r"-\d{6,}$", "", slug)
            slug = re.sub(r"-tickets$", "", slug)
            fallback_title = slug.replace("-", " ").title()
            if not fallback_title or len(fallback_title) < 4:
                return None

            def _fallback() -> RawEvent:
                seen_ids.add(eid)
                return RawEvent(
                    source=self.source_name,
                    source_id=eid,
                    title=fallback_title,
                    description=None,
                    start_datetime=None,
                    end_datetime=None,
                    location_text=None,
                    is_virtual=False,
                    url=clean_url,
                    city=None,
                    state=None,
                    raw_data={"id": eid, "url": clean_url},
                )

            async with sem:
                try:
                    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                        resp = await client.get(
                            clean_url,
                            headers={
                                "User-Agent": (
                                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                                    "Chrome/121.0.0.0 Safari/537.36"
                                ),
                                "Accept": "text/html,application/xhtml+xml",
                            },
                        )
                        if resp.status_code != 200:
                            logger.debug(
                                "Eventbrite enrich: HTTP %d for %s — using fallback",
                                resp.status_code, clean_url,
                            )
                            return _fallback()
                        html = resp.text
                except Exception as exc:
                    logger.debug("Eventbrite enrich: fetch failed for %s: %s", clean_url, exc)
                    return _fallback()

            soup = BeautifulSoup(html, "html.parser")
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = _json.loads(script.string or "")
                except Exception:
                    continue
                if not isinstance(data, dict) or data.get("@type") not in _EVENT_TYPES:
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
                logger.debug("Eventbrite enrich: got rich data for %r", name)
                return RawEvent(
                    source=self.source_name,
                    source_id=eid,
                    title=name,
                    description=description,
                    start_datetime=start_date,
                    end_datetime=end_date,
                    location_text=location_text,
                    is_virtual=False,
                    url=clean_url,
                    city=city,
                    state=state,
                    raw_data=data,
                )

            # No suitable JSON-LD found
            return _fallback()

        results = await asyncio.gather(*[_fetch_one(h) for h in unique_hrefs])
        events = [r for r in results if r is not None]
        logger.info(
            "Eventbrite enrich: enriched %d events from %d hrefs",
            len(events), len(unique_hrefs),
        )
        return events

    def _parse_hrefs(self, hrefs: list[str], seen_ids: set) -> list[RawEvent]:
        """Parse event URLs into RawEvents — all logic in Python, no JS complexity."""
        events: list[RawEvent] = []
        seen_urls: set[str] = set()
        for href in hrefs:
            # Strip query/fragment, keep clean path
            clean = href.split("?")[0].split("#")[0].rstrip("/")
            if clean in seen_urls:
                continue
            seen_urls.add(clean)

            # Extract numeric event ID from end of path (≥6 digits)
            m = re.search(r"-(\d{6,})$", clean)
            if not m:
                continue
            eid = m.group(1)
            if eid in seen_ids:
                continue
            seen_ids.add(eid)

            # Derive a human-readable title from the URL slug.
            # Path looks like: /e/some-event-name-tickets-123456789
            slug = clean.rsplit("/", 1)[-1]          # "some-event-name-tickets-123456789"
            slug = re.sub(r"-\d{6,}$", "", slug)     # remove trailing ID
            slug = re.sub(r"-tickets$", "", slug)     # remove "-tickets" suffix
            title = slug.replace("-", " ").title()

            if not title or len(title) < 4:
                continue

            events.append(
                RawEvent(
                    source=self.source_name,
                    source_id=eid,
                    title=title,
                    description=None,
                    start_datetime=None,
                    end_datetime=None,
                    location_text=None,
                    is_virtual=False,
                    url=clean,
                    city=None,
                    state=None,
                    raw_data={"id": eid, "url": clean},
                )
            )
            if len(events) >= 50:
                break
        return events

    def _parse_items(self, raw_items: list[dict], seen_ids: set) -> list[RawEvent]:
        events: list[RawEvent] = []
        for item in raw_items[:50]:
            eid = str(item.get("id", ""))
            if not eid or eid in seen_ids:
                continue
            seen_ids.add(eid)

            city = item.get("city") or None
            state = item.get("state") or None
            location_text = item.get("locationText") or None

            if not city and location_text:
                city, state = _parse_city_state(location_text)

            events.append(
                RawEvent(
                    source=self.source_name,
                    source_id=eid,
                    title=item.get("title", ""),
                    description=item.get("description"),
                    start_datetime=item.get("startDt"),
                    end_datetime=item.get("endDt"),
                    location_text=location_text,
                    is_virtual=item.get("isOnline", False),
                    url=item.get("url", ""),
                    city=city,
                    state=state,
                    raw_data=item,
                )
            )
        return events
