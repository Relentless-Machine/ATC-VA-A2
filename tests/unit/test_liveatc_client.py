from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.liveatc_client import LiveATCHTTPClient


class _Resp:
    def __init__(self, text: str, status_code: int = 200, url: str = "https://www.liveatc.net"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", self.url)
            response = httpx.Response(self.status_code, request=request, text=self.text)
            raise httpx.HTTPStatusError("http error", request=request, response=response)


@pytest.mark.asyncio
async def test_resolve_realtime_stream_url():
    client = LiveATCHTTPClient()
    http_client = AsyncMock()
    http_client.get = AsyncMock(
        side_effect=[
            _Resp('<a href="/listen.php?icao=vhhh">listen</a>'),
            _Resp('<a href="https://audio.example/vhhh_stream.mp3">stream</a>'),
        ]
    )
    url = await client.resolve_realtime_stream_url(http_client, "VHHH")
    assert url == "https://audio.example/vhhh_stream.mp3"


@pytest.mark.asyncio
async def test_list_historical_links():
    client = LiveATCHTTPClient()
    http_client = AsyncMock()
    http_client.get = AsyncMock(
        side_effect=[
            _Resp("blocked", status_code=403, url="https://www.liveatc.net/search/?icao=VHHH"),
            _Resp('<a href="/recordings/abc.mp3">abc</a><a href="/recordings/def.mp3">def</a>'),
            _Resp("index"),
        ]
    )
    links = await client.list_historical_links(http_client, "VHHH")
    urls = sorted(item.url for item in links)
    assert urls == [
        "https://www.liveatc.net/recordings/abc.mp3",
        "https://www.liveatc.net/recordings/def.mp3",
    ]


@pytest.mark.asyncio
async def test_list_historical_links_from_plain_filename_text():
    client = LiveATCHTTPClient()
    http_client = AsyncMock()
    http_client.get = AsyncMock(
        side_effect=[
            _Resp("blocked", status_code=403, url="https://www.liveatc.net/search/?icao=VHHH"),
            _Resp("VHHH5-App-Dep-Dir-Zone-Apr-13-2026-0000Z.mp3 (31:56)"),
            _Resp("index"),
        ]
    )
    links = await client.list_historical_links(http_client, "VHHH")
    urls = sorted(item.url for item in links)
    assert (
        "https://archive.liveatc.net/vhhh5/VHHH5-App-Dep-Dir-Zone-Apr-13-2026-0000Z.mp3" in urls
    )
