"""Shared pytest fixtures."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
async def no_tenacity_sleep():
    """Patch asyncio.sleep so tenacity retry waits are instant in all tests."""
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_sleep.return_value = None
        yield


@pytest.fixture(autouse=True)
def no_rate_limiter_sleep():
    """Patch time.sleep so geopy RateLimiter delays are instant in all tests."""
    with patch("time.sleep", return_value=None):
        yield
