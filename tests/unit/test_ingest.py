"""LiveATCIngestionService 单元测试 — Mock DB Session，预留 LiveATC 网络接口桩。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingestion_service import LiveATCIngestionService


def _utc(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: None)
    return db


@pytest.mark.asyncio
async def test_register_realtime_capture(mock_db):
    """register_realtime_capture 应向 DB 添加一条 VoiceFile 记录并 commit。"""
    svc = LiveATCIngestionService(mock_db)
    await svc.register_realtime_capture(
        file_name="live_001.mp3",
        file_path="/audio/live_001.mp3",
        start_time_utc=_utc(2024, 1, 1, 0),
        end_time_utc=_utc(2024, 1, 1, 0, 30),
        source_url="http://liveatc.example/feed",
        file_size=1024,
        duration_ms=1800000,
    )
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_historical_capture(mock_db):
    """register_historical_capture 应创建存储目录并写入 DB 记录。"""
    svc = LiveATCIngestionService(mock_db)
    with patch("app.services.ingestion_service.Path.mkdir"):
        await svc.register_historical_capture(
            file_name="hist_001.mp3",
            source_url="http://liveatc.example/archive/hist_001.mp3",
            start_time_utc=_utc(2024, 1, 1, 0),
            end_time_utc=_utc(2024, 1, 1, 1),
        )
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 预留接口桩：真实 LiveATC 网络抓取（RQ-A-2-10 / RQ-A-2-20）
# 当接入真实 LiveATC 时，取消注释并实现以下测试。
# ---------------------------------------------------------------------------
# @pytest.mark.asyncio
# async def test_fetch_realtime_stream_stub(mock_db):
#     """TODO: Mock httpx 请求，验证实时流抓取逻辑（RQ-A-2-10）。"""
#     pass
#
# @pytest.mark.asyncio
# async def test_schedule_historical_download_stub(mock_db):
#     """TODO: Mock httpx 请求，验证历史下载任务调度（RQ-A-2-20）。"""
#     pass
