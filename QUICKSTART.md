# Attendable — Quickstart Guide

> Get from install to your first event list in under 5 minutes.

---

## 1. What is Attendable?

Attendable is an AI-powered event discovery tool that finds, classifies, and surfaces tech & business intelligence events near you — all served in a local browser UI. It scrapes Eventbrite, Meetup, Luma, and the wider web, uses an LLM to filter out irrelevant events, and presents results in a sortable list and calendar view with interest tracking. All data stays on your machine.

---

## 2. Requirements

- [Pinokio](https://pinokio.computer) — one-click launcher
- An LLM API key **OR** [LM Studio](https://lmstudio.ai) for fully local operation
- ~500 MB disk space for Chromium (installed automatically)

---

## 3. Install & Start (Pinokio)

1. Open Pinokio → **Community** → search **Attendable** → click **Download**
2. Click **Install** — installs Python dependencies, Chromium, and initialises the database (~2 min)
3. Click **Start** → your browser opens at `http://localhost:8000`
4. A blue welcome banner appears → click **Start Setup →**

---

## 4. Configure (first-run wizard — ~2 min)

The wizard walks you through 5 steps:

| Step | What to enter | Notes |
|------|---------------|-------|
| **1 — Location** | Your ZIP code + radius (50–120 mi is typical) | Optional: lat/lon for precise distance calculation |
| **2 — Sources** | Leave all checked (Eventbrite, Meetup, Luma, Web Search) | Add custom search terms here or later |
| **3 — LLM** | Choose provider → paste API key → click **Test Connection** | See your provider's docs for the API key; local LM Studio needs no key |
| **4 — Search** | DuckDuckGo works out of the box (free, no key) | Add a Brave Search API key for better results |
| **5 — Schedule** | Leave defaults (daily 6 AM pipeline, weekly cleanup Sunday) | Click **Finish** |

---

## 5. Run your first pipeline

Click **▶ Run Pipeline** in the header. Watch the per-scraper progress indicators (2–5 min total).

When complete, the header shows: **✓ Done — N new · M updated** and event cards populate.

> **Tip:** If you see 0 events on the first run, that's normal. Web search discovers event page URLs on pass 1 and scrapes them on pass 2. Click **▶ Run Pipeline** a second time.

---

## 6. What you'll see

- **Event list** — cards sorted by date and distance; physical events show a distance badge
- **This Week strip** — color-coded urgency cards for events in the next 7 days (physical = red/amber/green, virtual = blue)
- **Calendar view** — toggle in the top-right corner; navigate by month
- **Interest tracking** — flag events 🚩 **Interested** / ☑ **Attending** / dismiss with 👁; dismissed events are hidden by default
- **Filter bar** — filter by source, type, distance, free-only, and tags (Ctrl/⌘+click for multi-select)

---

## 7. Tips

| What | How |
|------|-----|
| Change any setting | **Settings ⚙** (gear icon) → tabbed panel: Location, Sources, LLM, Search, Interests, Schedule |
| Sharpen searches with your interests | **Settings ⚙ → Interests** tab → paste a paragraph about your work; the LLM extracts keyword chips |
| Export to your calendar | Click **📅** → choose All / Flagged / Attending → downloads an `.ics` file |
| Re-run the setup wizard | **Settings ⚙ → Run Setup Wizard** button |
| Update Attendable | Click **Update** in Pinokio — your `.env` and `config.json` are preserved |
| Add search terms without restarting | Open the **🏷 Tags** popout → type a term → click **+** |

---

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| 0 events after first run | Web search needs a full pass to discover links; run the pipeline again or widen your radius |
| LLM test connection fails | Check your API key and account credits; verify the provider's status page |
| Playwright / Chromium errors | Run `uv run playwright install chromium` in the project folder |
| Pipeline stuck on "Running…" | Refresh the page — the run continues in the background (up to 10 min); check the terminal for errors |
| `config.json` errors on start | Delete `config.json` and restart — settings reset to defaults |
| Meetup returns no results | Meetup uses Playwright; ensure Chromium is installed (`uv run playwright install chromium`) |

---

For full configuration options and the API reference, see the [README](README.md).
