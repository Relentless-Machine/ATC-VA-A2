"""A-3 integration route tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import VoiceFile

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_request_processing_requires_token(client, voice_file_id):
    resp = await client.post("/api/v1/a3/request-processing", json={"voice_file_id": voice_file_id})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_request_processing_success(client, voice_file_id, a3_callback_headers):
    resp = await client.post(
        "/api/v1/a3/request-processing",
        json={"voice_file_id": voice_file_id},
        headers=a3_callback_headers,
    )
    assert resp.status_code == 202
    payload = resp.json()
    assert payload["voice_file_id"] == voice_file_id
    assert payload["status"] == 1


@pytest.mark.asyncio
async def test_get_status_success(client, voice_file_id):
    resp = await client.get(f"/api/v1/a3/status/{voice_file_id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["voice_file_id"] == voice_file_id
    assert "status_text" in payload


@pytest.mark.asyncio
async def test_retry_requires_token(client, voice_file_id):
    resp = await client.post(f"/api/v1/a3/retry/{voice_file_id}", json={"voice_file_id": voice_file_id, "attempt": 0})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_retry_success(client, db_session, voice_file_id, a3_callback_headers):
    voice_file = await db_session.get(VoiceFile, voice_file_id)
    voice_file.a3_process_status = 3
    voice_file.error_log = "boom"
    await db_session.commit()

    with patch("app.services.a3_integration_service.asyncio.sleep", new=AsyncMock()):
        resp = await client.post(
            f"/api/v1/a3/retry/{voice_file_id}",
            json={"voice_file_id": voice_file_id, "attempt": 0},
            headers=a3_callback_headers,
        )
    assert resp.status_code == 202
    payload = resp.json()
    assert payload["voice_file_id"] == voice_file_id
    assert payload["status"] == 1


@pytest.mark.asyncio
async def test_retry_rejects_non_failed_status(client, voice_file_id, a3_callback_headers):
    with patch("app.services.a3_integration_service.asyncio.sleep", new=AsyncMock()) as mocked_sleep:
        resp = await client.post(
            f"/api/v1/a3/retry/{voice_file_id}",
            json={"voice_file_id": voice_file_id, "attempt": 0},
            headers=a3_callback_headers,
        )

    assert resp.status_code == 400
    assert "Only failed A-3 processing can be retried" in resp.json()["detail"]
    mocked_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_annotations_success(client, voice_file_id):
    resp = await client.post(f"/api/v1/a3/sync-annotations/{voice_file_id}")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["voice_file_id"] == voice_file_id
    assert "ready_for_annotation" in payload


@pytest.mark.asyncio
async def test_queue_returns_items(client, voice_file_id):
    resp = await client.get("/api/v1/a3/queue", params={"status_filter": 0, "limit": 10})
    assert resp.status_code == 200
    payload = resp.json()
    assert "queue_size" in payload
    assert isinstance(payload["items"], list)
