"""ingestion 路由集成测试 — 验证实时/历史录音注册接口。"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_register_realtime_file(client):
    """POST /realtime/register 成功返回 201 及 voice_file_id。"""
    payload = {
        "file_name": "live_001.mp3",
        "file_path": "/audio/live_001.mp3",
        "start_time_utc": "2024-01-01T00:00:00Z",
        "end_time_utc": "2024-01-01T00:30:00Z",
        "source_url": "http://liveatc.example/feed",
        "file_size": 1024,
        "duration_ms": 1800000,
    }
    resp = await client.post("/api/v1/ingestion/realtime/register", json=payload)
    assert resp.status_code == 201
    assert "voice_file_id" in resp.json()


@pytest.mark.asyncio
async def test_register_historical_file(client):
    """POST /historical/register 成功返回 201 及 voice_file_id。"""
    payload = {
        "file_name": "hist_001.mp3",
        "source_url": "http://liveatc.example/archive/hist_001.mp3",
        "start_time_utc": "2024-01-01T00:00:00Z",
        "end_time_utc": "2024-01-01T01:00:00Z",
    }
    with patch("app.services.ingestion_service.Path.mkdir"):
        resp = await client.post("/api/v1/ingestion/historical/register", json=payload)
    assert resp.status_code == 201
    assert "voice_file_id" in resp.json()


# ---------------------------------------------------------------------------
# 预留接口桩：LiveATC 实时监听与历史下载任务调度（RQ-A-2-10 / RQ-A-2-20）
# ---------------------------------------------------------------------------
# @pytest.mark.asyncio
# async def test_trigger_realtime_listen_stub(client):
#     """TODO: 接入真实 LiveATC 后，验证实时监听触发接口（RQ-A-2-10）。"""
#     pass
#
# @pytest.mark.asyncio
# async def test_trigger_historical_download_stub(client):
#     """TODO: 接入真实 LiveATC 后，验证历史下载任务调度接口（RQ-A-2-20）。"""
#     pass


@pytest.mark.asyncio
async def test_scheduler_status(client):
    resp = await client.get("/api/v1/ingestion/scheduler/status")
    assert resp.status_code == 200
    assert "running" in resp.json()


@pytest.mark.asyncio
async def test_trigger_historical_download(client):
    with patch("app.api.routes.ingestion.liveatc_scheduler.trigger_historical_once", AsyncMock(return_value=2)):
        resp = await client.post("/api/v1/ingestion/scheduler/trigger/historical")
    assert resp.status_code == 200
    assert resp.json()["downloaded"] == 2
    assert "error" in resp.json()


@pytest.mark.asyncio
async def test_trigger_realtime_once(client):
    with patch("app.api.routes.ingestion.liveatc_scheduler.trigger_realtime_once", AsyncMock(return_value=True)):
        resp = await client.post("/api/v1/ingestion/scheduler/trigger/realtime")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "error" in resp.json()
