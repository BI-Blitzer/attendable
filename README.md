# Attendable

AI-powered tech & business intelligence event discovery. Scrapes Eventbrite, Meetup, Luma, and the web, classifies events with an LLM, and serves them in a browser UI with list and calendar views.

---

## Features

- **Multi-source scraping** — Eventbrite, Meetup, Luma, and AI-guided web search
- **LLM classification** — filters and tags events by industry/technology topic
- **Distance filtering** — keeps events within your configured radius
- **Browser UI** — list view, calendar view, "This Week" urgency strip, interest tracking (flag / attend / dismiss)
- **Tags popout** — filter by tag with live counts; add custom geo search terms directly from the UI
- **iCal export** — download `.ics` for Google Calendar / Apple Calendar; modal lets you filter by All / Flagged / Attending
- **Settings panel** — gear icon opens a full settings form; "Run Setup Wizard" button inside for step-by-step re-configuration
- **First-run banner** — welcome banner on first load links to the setup wizard; dismissible once configured
- **Scheduled runs** — daily pipeline + weekly cleanup via APScheduler; configurable from Settings
- **SQLite by default** — no database server required; PostgreSQL supported for production
- **Fully local mode** — works with LM Studio + SearXNG, zero cloud dependency

---

## Quickstart — Pinokio (one-click)

1. Open [Pinokio](https://pinokio.computer) and click **Discover**
2. Find **Attendable** and click **Install**
3. Click **Start** → browser opens at `http://localhost:8000`
4. A welcome banner appears on first load — click **Start Setup →** to configure your LLM key, location, and sources

### Pinokio actions

| Button | What it does |
|--------|-------------|
| **Install** | Installs Python dependencies, Chromium (for scrapers), initialises the database, and copies `.env.local.example → .env` *(skipped if `.env` already exists)* |
| **Start** | Starts the web server and opens `http://localhost:8000` in your browser |
| **Update** | Pulls the latest code (`git pull`), updates dependencies, and applies any new database migrations. **Your `.env` and `config.json` are left untouched.** |
| **Factory Reset** | Deletes all local data (`.env`, `config.json`, database, backups), resets the code to the latest clean version from the repository, then runs a full reinstall with a fresh `.env` from the template. Use this to start completely from scratch. |

---

## Quickstart — Manual

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Chromium for Playwright scrapers (installed below)

### Setup

```bash
# 1. Clone and install
git clone <repo-url>
cd event_agent
uv sync

# 2. Install Chromium (needed for Meetup and Eventbrite scrapers)
uv run playwright install chromium

# 3. Configure
cp .env.example .env
# Edit .env — set at least one LLM key

# 4. Initialize the database
uv run python main.py db init

# 5. Start the server
uv run python main.py serve
# → http://localhost:8000
```

### Run a pipeline pass manually

```bash
uv run python main.py run                     # all sources
uv run python main.py run --source eventbrite # single source
```

---

## Configuration

Copy `.env.example` (cloud APIs) or `.env.local.example` (fully local) to `.env`.

All settings are also patchable live via `PATCH /config` from the UI settings panel (⚙ gear icon).

### LLM providers

| Provider | Model string | Key env var |
|---|---|---|
| Anthropic | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Google | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| LM Studio | `openai/meta-llama-3.1-8b-instruct` | `LLM_API_BASE=http://localhost:1234/v1` |
| Ollama | `ollama/llama3` | `LLM_API_BASE=http://localhost:11434` |

### Search providers (in priority order)

| Provider | Cost | Setup |
|---|---|---|
| [Brave Search](https://brave.com/search/api) | Free tier (2k/month) | `BRAVE_API_KEY` |
| [SerpAPI](https://serpapi.com) | Paid | `SERP_API_KEY` |
| [SearXNG](https://searxng.github.io/searxng/) | Free, self-hosted | `SEARXNG_URL=http://localhost:8888/search` |
| DuckDuckGo | Free, no key | automatic fallback |

### Geographic config

```env
CENTER_ZIP=10001       # your ZIP code (e.g. 10001 = Midtown Manhattan)
RADIUS_MILES=120       # search radius
CENTER_LAT=            # optional: override ZIP centroid
CENTER_LON=            # optional: override ZIP centroid
```

### Keywords

Two keyword lists control what gets searched:

| Setting | Purpose |
|---|---|
| `search_keywords` | Geo-targeted (appends ZIP to query). For local physical/hybrid events. |
| `user_keywords` | Additional geo-targeted terms added by the user via the Tags popout. |
| `vendor_virtual_keywords` | Searched globally (no ZIP). For vendor webinars and online events. |

Custom terms can be added without restarting — type into the **🏷 Tags** popout and click **+**. They appear in the "No events yet" section until the next pipeline run discovers matching events.

---

## Fully Local Mode (no cloud required)

1. Install [LM Studio](https://lmstudio.ai), load a 7B+ model, enable the local server
2. (Optional) Self-host [SearXNG](https://searxng.github.io/searxng/) for private web search — set `SEARXNG_URL` in `.env`; DuckDuckGo is the automatic fallback if unset
3. Use `.env.local.example` as your `.env`

---

## PostgreSQL (production)

If you prefer PostgreSQL over SQLite:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/event_agent
```

To migrate existing PostgreSQL data to SQLite:

```bash
PG_SOURCE_URL=postgresql+psycopg2://... uv run python scripts/migrate_pg_to_sqlite.py
```

---

## Development

```bash
uv run pytest tests/ -v    # run tests (48 tests)
uv run python main.py db migrate -m "description"  # new migration
```

### Project layout

```
event_agent/
  agents/       # LLM agents: classifier, location, discovery, crew pipeline
  api/          # FastAPI app, routes, scheduler
  config/       # Pydantic settings
  db/           # SQLAlchemy models, repository, engine
  scrapers/     # Eventbrite, Meetup, Luma, web search
alembic/        # DB migrations
scripts/        # One-off utilities (PG→SQLite export)
tests/          # pytest suite
main.py         # CLI entry point (Click)
```

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Browser UI |
| `GET` | `/events` | List events (filterable) |
| `GET` | `/events/count` | Count matching events |
| `GET` | `/events/export.ics` | iCal export of current filter view |
| `GET` | `/events/{id}` | Event detail |
| `PATCH` | `/events/{id}/interest` | Set interest status (`noted`/`interested`/`attending`) |
| `GET` | `/tags` | All tags with event counts |
| `POST` | `/run` | Trigger pipeline run |
| `GET` | `/run/{id}` | Poll run status |
| `GET` | `/stats` | Last-run stats + API key status |
| `GET` | `/config` | Current merged config |
| `PATCH` | `/config` | Patch runtime config (persisted to `config.json`) |
| `GET` | `/setup/status` | Whether first-run setup is needed |
| `POST` | `/setup/` | Save wizard env vars + config vars |
| `POST` | `/setup/test-llm` | Test LLM API key connectivity |
| `POST` | `/setup/test-search` | Test search provider connectivity |
| `POST` | `/backup` | Download backup ZIP |
| `POST` | `/backup/restore` | Restore from backup ZIP |

---

## CLI reference

```
uv run python main.py run              # full pipeline (all sources)
uv run python main.py run --source X  # single source
uv run python main.py serve           # start web server on :8000
uv run python main.py db init         # apply migrations
uv run python main.py db migrate -m   # create new migration
uv run python main.py db cleanup      # delete events older than N days
```
