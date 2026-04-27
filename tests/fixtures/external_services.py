from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest


@pytest.fixture
def network_guard() -> Callable[[Awaitable[Any]], Awaitable[Any]]:
    async def _network_guard(coro: Awaitable[Any]) -> Any:
        try:
            return await asyncio.wait_for(coro, timeout=45)
        except (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError, httpx.RequestError) as exc:
            pytest.skip(f"LiveATC network unavailable or too slow: {exc}")

    return _network_guard


@pytest.fixture
def scheduler_status_payload() -> Callable[[bool], dict[str, str | bool | int | None]]:
    def _build(running: bool) -> dict[str, str | bool | int | None]:
        return {
            "running": running,
            "icao_code": "VHHH",
            "last_error": None,
            "last_realtime_at": None,
            "last_historical_at": None,
            "last_historical_found": 0,
            "last_historical_skipped": 0,
            "last_historical_downloaded": 0,
        }

    return _build
