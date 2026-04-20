"""callback 路由集成测试 — A-5 用户与航迹外键联调预留。"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select

from app.core.config import settings
from app.db.models import VoiceFile, VoiceSegment


def _utc(h=0):
    return datetime(2024, 1, 1, h, tzinfo=timezone.utc)


@pytest_asyncio.fixture
async def voice_file_id(db_session) -> int:
    """前置数据：插入一条 VoiceFile，返回其 id。"""
    result = await db_session.execute(
        insert(VoiceFile).values(
            file_name="cb_test.mp3",
            file_path="/audio/cb_test.mp3",
            icao_code="VHHH",
            start_time_utc=_utc(0),
            end_time_utc=_utc(1),
            status=1,
            a3_process_status=0,
            duration_ms=3600000,
            last_access_at=_utc(0),
            created_at=_utc(0),
            updated_at=_utc(0),
        )
    )
    await db_session.commit()
    return result.inserted_primary_key[0]


@pytest.mark.asyncio
async def test_callback_success_201(client, voice_file_id):
    """合法 payload + 正确 Token → 201，segments 写入 DB。"""
    payload = {
        "voice_file_id": voice_file_id,
        "process_status": 2,
        "segments": [
            {"relative_start": 0.0, "relative_end": 1.5, "asr_content": "alpha"},
            {"relative_start": 1.5, "relative_end": 3.0, "asr_content": "bravo"},
        ],
    }
    resp = await client.post(
        "/api/v1/a3/callback",
        json=payload,
        headers={"X-A3-Token": settings.a3_callback_token},
    )
    assert resp.status_code == 201
    assert resp.json()["segment_count"] == 2


@pytest.mark.asyncio
async def test_callback_invalid_token_401(client, voice_file_id):
    """错误 Token → 401。"""
    resp = await client.post(
        "/api/v1/a3/callback",
        json={"voice_file_id": voice_file_id, "process_status": 2, "segments": []},
        headers={"X-A3-Token": "wrong-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_callback_missing_token_401(client, voice_file_id):
    """不携带 Token → 401。"""
    resp = await client.post(
        "/api/v1/a3/callback",
        json={"voice_file_id": voice_file_id, "process_status": 2, "segments": []},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_callback_fk_missing_404(client):
    """voice_file_id 不存在 → 404，不崩溃。"""
    resp = await client.post(
        "/api/v1/a3/callback",
        json={"voice_file_id": 99999, "process_status": 2, "segments": []},
        headers={"X-A3-Token": settings.a3_callback_token},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_callback_idempotent_upsert(client, db_session, voice_file_id):
    payload = {
        "voice_file_id": voice_file_id,
        "process_status": 2,
        "segments": [
            {"relative_start": 0.0, "relative_end": 2.0, "asr_content": "first"},
        ],
    }
    headers = {"X-A3-Token": settings.a3_callback_token}

    first = await client.post("/api/v1/a3/callback", json=payload, headers=headers)
    assert first.status_code == 201

    payload["segments"][0]["asr_content"] = "updated"
    second = await client.post("/api/v1/a3/callback", json=payload, headers=headers)
    assert second.status_code == 201

    count = await db_session.execute(
        select(func.count()).select_from(VoiceSegment).where(
            VoiceSegment.voice_file_id == voice_file_id,
            VoiceSegment.relative_start == 0.0,
            VoiceSegment.relative_end == 2.0,
        )
    )
    assert count.scalar_one() == 1


# ---------------------------------------------------------------------------
# 预留接口桩：A-5 用户与航迹外键联调（track_id / author_id）
# ---------------------------------------------------------------------------
# @pytest.mark.asyncio
# async def test_callback_with_track_id_stub(client, voice_file_id):
#     """TODO: A-5 联调 — 验证 VoiceFile.track_id 外键关联航迹表。"""
#     pass
#
# @pytest.mark.asyncio
# async def test_segment_author_id_stub(client, voice_file_id):
#     """TODO: A-5 联调 — 验证 VoiceSegment.author_id 外键关联用户表。"""
#     pass
