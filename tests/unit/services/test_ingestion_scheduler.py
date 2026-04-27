"""LiveATCScheduler 单元测试。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ingestion_scheduler import LiveATCScheduler

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_start_and_stop_scheduler_lifecycle():
    scheduler = LiveATCScheduler()

    with patch.object(scheduler, "_realtime_loop", new=AsyncMock()), patch.object(
        scheduler, "_historical_loop", new=AsyncMock()
    ):
        await scheduler.start()
        assert scheduler.status()["running"] is True
        assert scheduler._realtime_task is not None
        assert scheduler._historical_task is not None

        await scheduler.stop()

    assert scheduler.status()["running"] is False
    assert scheduler._realtime_task is None
    assert scheduler._historical_task is None


@pytest.mark.asyncio
async def test_start_is_idempotent():
    scheduler = LiveATCScheduler()

    with patch.object(scheduler, "_realtime_loop", new=AsyncMock()), patch.object(
        scheduler, "_historical_loop", new=AsyncMock()
    ):
        await scheduler.start()
        first_realtime_task = scheduler._realtime_task
        first_historical_task = scheduler._historical_task

        await scheduler.start()

        assert scheduler._realtime_task is first_realtime_task
        assert scheduler._historical_task is first_historical_task
        await scheduler.stop()


@pytest.mark.asyncio
async def test_trigger_realtime_once_sets_error_when_exception():
    scheduler = LiveATCScheduler()

    with patch.object(scheduler, "_run_realtime_once", new=AsyncMock(side_effect=RuntimeError("boom"))):
        ok = await scheduler.trigger_realtime_once()

    assert ok is False
    assert scheduler.status()["last_error"] == "realtime: boom"


@pytest.mark.asyncio
async def test_trigger_historical_once_sets_error_when_exception():
    scheduler = LiveATCScheduler()

    with patch.object(scheduler, "_run_historical_once", new=AsyncMock(side_effect=RuntimeError("boom"))):
        downloaded = await scheduler.trigger_historical_once()

    assert downloaded == 0
    assert scheduler.status()["last_error"] == "historical: boom"


def test_backoff_delay_respects_range_and_max():
    scheduler = LiveATCScheduler()

    with patch("app.services.ingestion_scheduler.random.uniform", return_value=0.2):
        delay_0 = scheduler._backoff_delay(0)
        delay_3 = scheduler._backoff_delay(3)

    assert 0.1 <= delay_0 <= 30.0
    assert 0.1 <= delay_3 <= 30.0
    assert delay_3 >= delay_0


def test_status_formats_datetime_fields():
    scheduler = LiveATCScheduler()
    now = datetime.now(timezone.utc)
    scheduler._last_realtime_at = now
    scheduler._last_historical_at = now

    status = scheduler.status()
    assert status["last_realtime_at"] == now.isoformat()
    assert status["last_historical_at"] == now.isoformat()
