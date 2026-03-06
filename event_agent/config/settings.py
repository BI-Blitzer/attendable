"""Application settings loaded from environment / .env file."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Geographic
    center_zip: str = "10001"
    radius_miles: int = 120
    center_lat: float | None = None  # if set, overrides ZIP centroid for distance calc
    center_lon: float | None = None

    # Provider-specific API keys (read automatically by LiteLLM)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    eventbrite_api_key: str = ""
    meetup_api_key: str = ""
    serp_api_key: str = ""
    brave_api_key: str = ""

    # LLM config — model string follows LiteLLM conventions:
    #   claude-sonnet-4-6              → Anthropic (needs ANTHROPIC_API_KEY)
    #   gpt-4o                         → OpenAI    (needs OPENAI_API_KEY)
    #   gemini/gemini-2.0-flash        → Google    (needs GEMINI_API_KEY)
    #   ollama/llama3                  → Ollama    (needs LLM_API_BASE)
    llm_model: str = "claude-sonnet-4-6"
    llm_api_key: str = ""       # optional explicit override; otherwise uses provider env var
    llm_api_base: str = ""      # optional; required for Ollama (http://localhost:11434)

    # Database
    database_url: str = "sqlite+aiosqlite:///event_agent.db"

    # SearXNG (optional self-hosted search)
    searxng_url: str = ""

    # Scraping
    enabled_sources: list[str] = ["eventbrite", "meetup", "luma", "web_search"]
    search_keywords: list[str] = [
        "technology conference",
        "AI conference",
        "data analytics conference",
        "digital transformation conference",
        "business conference",
        "executive leadership summit",
        "sales conference",
        "product management conference",
        "startup summit",
        "manufacturing conference",
        "industrial automation conference",
        "supply chain conference",
        "robotics conference",
        "operations management conference",
        "fintech conference",
        "investment conference",
    ]
    user_keywords: list[str] = []   # user-added custom geo search terms

    # Virtual/vendor-specific keywords — searched globally (no geo restriction).
    # Results are expected to be online events so the location filter is bypassed.
    # Scheduled pipeline runs
    schedule_enabled: bool = True
    schedule_hour: int = 6    # 6 AM local server time
    schedule_minute: int = 0

    # Scheduled weekly cleanup
    cleanup_schedule_enabled: bool = True
    cleanup_day_of_week: int = 6   # APScheduler: 0=Mon … 6=Sun
    cleanup_schedule_hour: int = 3  # 3 AM
    cleanup_days_past: int = 30     # delete events ended >N days ago

    # Year is appended automatically by the scraper (current year, plus next year
    # from October onwards). Do not include a year in these strings.
    wizard_completed: bool = False   # set to True after first wizard run or dismiss

    vendor_virtual_keywords: list[str] = [
        "Qlik webinar",
        "Microsoft Fabric virtual event",
        "Microsoft Power BI webinar",
        "Google Cloud Next",
        "Snowflake Summit",
        "Databricks Data + AI Summit",
        "Tableau virtual event",
        "Anthropic developer event",
        "OpenAI developer event",
        "AWS analytics webinar",
        "NVIDIA GTC",
        "Microsoft Build",
        "Google I/O",
        "AWS re:Invent",
        "AUTOMATE robotics conference",
        "RoboBusiness conference",
        "industrial IoT virtual summit",
        "manufacturing technology webinar",
        "Gartner IT summit",
        "Forrester summit",
        "SaaStr Annual",
        "B2B sales conference",
        "fintech virtual summit",
        "product management summit",
        "growth marketing conference",
    ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
