"""A3CallbackService 单元测试 — Mock DB Session，不触碰真实数据库。"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.callback import A3CallbackRequest, A3SegmentPayload
from app.services.a3_callback_service import A3CallbackService

pytestmark = pytest.mark.unit


def _make_voice_file(fid: int = 1):
    vf = MagicMock()
    vf.id = fid
    vf.start_time_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    vf.updated_at = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    vf.a3_process_status = 0
    vf.error_log = None
    return vf


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_handle_callback_inserts_segments(mock_db):
    """正常回调：插入 2 条 segment，返回正确 segment_count。"""
    vf = _make_voice_file()
    mock_db.get = AsyncMock(return_value=vf)

    payload = A3CallbackRequest(
        voice_file_id=1,
        process_status=2,
        segments=[
            A3SegmentPayload(relative_start=0.0, relative_end=1.5, asr_content="alpha"),
            A3SegmentPayload(relative_start=1.5, relative_end=3.0, asr_content="bravo"),
        ],
    )

    svc = A3CallbackService(mock_db)
    resp = await svc.handle_callback(payload)

    assert resp.segment_count == 2
    assert mock_db.add.call_count == 2
    assert mock_db.execute.await_count == 2
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_callback_voice_file_not_found(mock_db):
    """voice_file_id 不存在时抛出 404。"""
    mock_db.get = AsyncMock(return_value=None)

    payload = A3CallbackRequest(voice_file_id=999, process_status=2, segments=[])
    svc = A3CallbackService(mock_db)

    with pytest.raises(HTTPException) as exc_info:
        await svc.handle_callback(payload)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_handle_callback_empty_segments(mock_db):
    """segments 为空时正常返回，segment_count=0，不调用 add。"""
    vf = _make_voice_file()
    mock_db.get = AsyncMock(return_value=vf)

    payload = A3CallbackRequest(voice_file_id=1, process_status=2, segments=[])
    svc = A3CallbackService(mock_db)
    resp = await svc.handle_callback(payload)

    assert resp.segment_count == 0
    mock_db.add.assert_not_called()
