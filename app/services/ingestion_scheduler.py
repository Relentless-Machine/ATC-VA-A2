from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.ingestion_service import LiveATCIngestionService
from app.services.liveatc_client import LiveATCHTTPClient


class LiveATCScheduler:
    def __init__(self):
        self.client = LiveATCHTTPClient()
        self._running = False
        self._realtime_task: asyncio.Task | None = None
        self._historical_task: asyncio.Task | None = None
        self._last_error: str | None = None
        self._last_realtime_at: datetime | None = None
        self._last_historical_at: datetime | None = None
        self._last_historical_found: int = 0
        self._last_historical_skipped: int = 0
        self._last_historical_downloaded: int = 0
        self._lock = asyncio.Lock()

    def _default_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": settings.a2_http_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": settings.a2_http_accept_language,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": settings.a2_liveatc_base_url,
        }
        if settings.a2_http_cookie.strip():
            headers["Cookie"] = settings.a2_http_cookie.strip()
        return headers

    def _http_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0)

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            self._running = True
            self._realtime_task = asyncio.create_task(self._realtime_loop(), name="liveatc-realtime-loop")
            self._historical_task = asyncio.create_task(self._historical_loop(), name="liveatc-historical-loop")

    async def stop(self) -> None:
        async with self._lock:
            self._running = False
            tasks = [t for t in (self._realtime_task, self._historical_task) if t]
            for task in tasks:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._realtime_task = None
            self._historical_task = None

    async def trigger_historical_once(self) -> int:
        try:
            return await self._run_historical_once()
        except Exception as exc:  # noqa: BLE001
            self._last_error = f"historical: {exc}"
            return 0

    async def trigger_realtime_once(self) -> bool:
        try:
            return await self._run_realtime_once()
        except Exception as exc:  # noqa: BLE001
            self._last_error = f"realtime: {exc}"
            return False

    def status(self) -> dict[str, str | bool | int | None]:
        return {
            "running": self._running,
            "icao_code": settings.a2_icao_code,
            "last_error": self._last_error,
            "last_realtime_at": self._fmt_time(self._last_realtime_at),
            "last_historical_at": self._fmt_time(self._last_historical_at),
            "last_historical_found": self._last_historical_found,
            "last_historical_skipped": self._last_historical_skipped,
            "last_historical_downloaded": self._last_historical_downloaded,
        }

    @staticmethod
    def _fmt_time(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    async def _realtime_loop(self) -> None:
        while self._running:
            try:
                await self._run_realtime_once()
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"realtime: {exc}"
            await asyncio.sleep(settings.a2_realtime_interval_seconds)

    async def _historical_loop(self) -> None:
        while self._running:
            try:
                await self._run_historical_once()
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"historical: {exc}"
            await asyncio.sleep(settings.a2_historical_interval_seconds)

    async def _run_realtime_once(self) -> bool:
        headers = self._default_headers()
        stream_url = None
        for _ in range(max(settings.a2_http_max_retries, 1)):
            try:
                async with httpx.AsyncClient(timeout=self._http_timeout(), headers=headers) as client:
                    stream_url = await self.client.resolve_realtime_stream_url(client, settings.a2_icao_code)
                if stream_url:
                    break
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"realtime resolve failed: {exc}"
                await asyncio.sleep(1)
        if not stream_url:
            self._last_error = "unable to resolve realtime stream url"
            return False
        async with SessionLocal() as db:
            svc = LiveATCIngestionService(db)
            row = await svc.capture_realtime_stream(stream_url=stream_url, request_headers=headers)
        if row is None:
            return False
        self._last_realtime_at = datetime.now(timezone.utc)
        self._last_error = None
        return True

    async def _run_historical_once(self) -> int:
        headers = self._default_headers()
        last_exc: Exception | None = None
        for _ in range(max(settings.a2_http_max_retries, 1)):
            try:
                async with httpx.AsyncClient(timeout=self._http_timeout(), headers=headers) as client:
                    links = await self.client.list_historical_links(client, settings.a2_icao_code)
                    self._last_historical_found = len(links)
                    self._last_historical_skipped = 0
                    self._last_historical_downloaded = 0
                    if not links:
                        return 0
                    saved = 0
                    skipped = 0
                    async with SessionLocal() as db:
                        svc = LiveATCIngestionService(db)
                        for item in links[: settings.a2_historical_max_files_per_run]:
                            if await svc.has_source_url(item.url):
                                skipped += 1
                                continue
                            resp = await client.get(item.url, follow_redirects=True)
                            if resp.status_code >= 400 or not resp.content:
                                continue
                            await svc.register_historical_download(
                                file_name=item.file_name,
                                source_url=item.url,
                                content=resp.content,
                            )
                            saved += 1
                    self._last_historical_skipped = skipped
                    self._last_historical_downloaded = saved
                    self._last_historical_at = datetime.now(timezone.utc)
                    self._last_error = None
                    return saved
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                await asyncio.sleep(1)
        if last_exc is not None:
            raise last_exc
        return 0


liveatc_scheduler = LiveATCScheduler()
