"""audio 路由集成测试 — 使用内存 DB，Mock asyncio.to_thread 避免真实文件读取。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import insert

from app.db.models import VoiceFile, VoiceSegment


def _utc(h=0, m=0):
    return datetime(2024, 1, 1, h, m, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def seeded_audio(db_session):
    """插入一条 VoiceFile + 一条 VoiceSegment 供流式接口使用。"""
    await db_session.execute(
        insert(VoiceFile).values(
            id=10,
            file_name="test.mp3",
            file_path="/audio/test.mp3",
            icao_code="VHHH",
            start_time_utc=_utc(0),
            end_time_utc=_utc(1),
            status=1,
            a3_process_status=2,
            duration_ms=3600000,
            last_access_at=_utc(0),
            created_at=_utc(0),
            updated_at=_utc(0),
        )
    )
    await db_session.execute(
        insert(VoiceSegment).values(
            id=20,
            voice_file_id=10,
            relative_start=0.0,
            relative_end=10.0,
            abs_start_time=_utc(0),
            abs_end_time=_utc(0, 1),
            is_annotated=False,
            created_at=_utc(0),
            updated_at=_utc(0),
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_stream_audio_returns_206(client, seeded_audio):
    """时间范围命中 segment 时返回 206 流式响应。"""
    class MockFile:
        def read(self, *args, **kwargs):
            return b""
        def close(self):
            pass

    async def fake_to_thread(fn, *args):
        if hasattr(fn, "__name__") and fn.__name__ == "_open_file":
            return MockFile()
        return fn(*args)

    with patch("app.services.query_service.asyncio.to_thread", side_effect=fake_to_thread):
        resp = await client.get(
            "/api/v1/audio/stream",
            params={
                "start_time_utc": "2024-01-01T00:00:00Z",
                "end_time_utc": "2024-01-01T00:30:00Z",
            },
        )
    assert resp.status_code == 206


@pytest.mark.asyncio
async def test_stream_audio_no_segment_404(client):
    """时间范围无 segment 时返回 404。"""
    resp = await client.get(
        "/api/v1/audio/stream",
        params={
            "start_time_utc": "2099-01-01T00:00:00Z",
            "end_time_utc": "2099-01-01T01:00:00Z",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_stream_audio_bad_range_400(client):
    """end_time <= start_time 时返回 400。"""
    resp = await client.get(
        "/api/v1/audio/stream",
        params={
            "start_time_utc": "2024-01-01T01:00:00Z",
            "end_time_utc": "2024-01-01T00:00:00Z",
        },
    )
    assert resp.status_code == 400
