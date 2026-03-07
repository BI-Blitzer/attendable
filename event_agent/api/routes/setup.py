"""Setup API routes — first-run wizard status and config write-through."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from event_agent.api.routes.config import _load_overrides, _save_overrides, _PATCHABLE
from event_agent.config.settings import get_settings

router = APIRouter(prefix="/setup", tags=["setup"])

_ENV_FILE = Path(".env")

_ALLOWED_ENV_KEYS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "XAI_API_KEY",
    "MISTRAL_API_KEY",
    "LLM_MODEL",
    "LLM_API_KEY",
    "LLM_API_BASE",
    "BRAVE_API_KEY",
    "SERP_API_KEY",
    "SEARXNG_URL",
}


@router.get("/status")
async def setup_status():
    s = get_settings()
    has_llm = bool(
        s.anthropic_api_key
        or s.openai_api_key
        or s.gemini_api_key
        or s.llm_api_base
        or s.llm_api_key
    )
    overrides = _load_overrides()
    wizard_completed = overrides.get("wizard_completed", False)

    # Identify active LLM provider for settings panel pre-selection
    llm_model = (s.llm_model or "").lower()
    if s.anthropic_api_key and not s.llm_api_base:
        active_llm = "anthropic"
    elif s.openai_api_key:
        active_llm = "openai"
    elif s.gemini_api_key:
        active_llm = "google"
    elif s.xai_api_key:
        active_llm = "grok"
    elif s.mistral_api_key:
        active_llm = "mistral"
    elif s.llm_api_base:
        if "11434" in s.llm_api_base:
            active_llm = "ollama"
        elif "1234" in s.llm_api_base:
            active_llm = "lmstudio"
        else:
            active_llm = "custom"
    elif "claude" in llm_model:
        active_llm = "anthropic"
    elif "gpt" in llm_model:
        active_llm = "openai"
    elif "gemini" in llm_model:
        active_llm = "google"
    elif "grok" in llm_model or "xai" in llm_model:
        active_llm = "grok"
    elif "mistral" in llm_model:
        active_llm = "mistral"
    else:
        active_llm = None

    # Identify active search provider
    if s.brave_api_key:
        active_search = "brave"
    elif s.serp_api_key:
        active_search = "serpapi"
    elif s.searxng_url:
        active_search = "searxng"
    else:
        active_search = "ddg"

    return {
        "needs_setup": not has_llm,
        "wizard_completed": wizard_completed,
        "active_llm": active_llm,
        "active_search": active_search,
        "configured": {
            "llm": has_llm,
            "search": bool(s.brave_api_key or s.serp_api_key or s.searxng_url),
            "location": bool(s.center_zip),
            "sources": bool(s.enabled_sources),
        },
    }


class SetupPayload(BaseModel):
    env_vars: dict[str, str] = {}
    config_vars: dict[str, object] = {}


@router.post("/")
async def post_setup(payload: SetupPayload):
    # Write env vars to .env and live environment
    bad_env = [k for k in payload.env_vars if k not in _ALLOWED_ENV_KEYS]
    if bad_env:
        raise HTTPException(400, f"Disallowed env key(s): {bad_env}")

    if payload.env_vars:
        # Ensure .env exists so set_key can write to it
        if not _ENV_FILE.exists():
            _ENV_FILE.touch()
        for k, v in payload.env_vars.items():
            set_key(str(_ENV_FILE), k, v)
            os.environ[k] = v
        # Invalidate settings cache so next call picks up new values
        get_settings.cache_clear()

    # Write config vars to config.json
    bad_cfg = [k for k in payload.config_vars if k not in _PATCHABLE]
    if bad_cfg:
        raise HTTPException(400, f"Disallowed config key(s): {bad_cfg}")

    if payload.config_vars:
        overrides = _load_overrides()
        overrides.update(payload.config_vars)
        _save_overrides(overrides)

    return {"ok": True}


class TestLlmPayload(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""
    api_base: str = ""


_PROVIDER_DEFAULTS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai":    "gpt-4o-mini",
    "google":    "gemini/gemini-2.0-flash",
    "grok":      "xai/grok-beta",
    "mistral":   "mistral/mistral-small-latest",
}


@router.post("/test-llm")
async def test_llm_connection(payload: TestLlmPayload):
    import litellm  # noqa: PLC0415
    model = payload.model or _PROVIDER_DEFAULTS.get(payload.provider, "claude-haiku-4-5-20251001")
    kwargs: dict = {}
    if payload.api_key:  kwargs["api_key"]  = payload.api_key
    if payload.api_base: kwargs["api_base"] = payload.api_base
    try:
        resp = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "Reply with only OK"}],
            max_tokens=5, **kwargs,
        )
        return {"ok": True, "reply": (resp.choices[0].message.content or "").strip()}
    except Exception as e:
        raise HTTPException(400, str(e))


class TestSearchPayload(BaseModel):
    provider: str
    api_key: str = ""
    url: str = ""


@router.post("/test-search")
async def test_search_connection(payload: TestSearchPayload):
    import httpx  # noqa: PLC0415
    try:
        if payload.provider == "brave":
            r = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": "tech conference", "count": 1},
                headers={"Accept": "application/json", "Accept-Encoding": "gzip",
                         "X-Subscription-Token": payload.api_key},
                timeout=10,
            )
            r.raise_for_status()
        elif payload.provider == "serpapi":
            r = httpx.get(
                "https://serpapi.com/search",
                params={"q": "tech conference", "num": 1, "api_key": payload.api_key},
                timeout=10,
            )
            r.raise_for_status()
        elif payload.provider == "searxng":
            base = (payload.url or "http://localhost:8080").rstrip("/")
            r = httpx.get(f"{base}/search", params={"q": "tech conference", "format": "json"}, timeout=10)
            r.raise_for_status()
        # ddg: always passes, no key needed
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))
